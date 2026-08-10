/*
 * gwyconvert — headless converter from any Gwyddion-supported SPM raw file
 * to Gwyddion's native .gwy format.
 *
 * Usage:
 *   gwyconvert INPUT OUTPUT.gwy    convert a raw file
 *   gwyconvert --list-formats      print registered file formats as JSON
 *
 * On successful conversion a single JSON object is printed on stdout:
 *   {"module": "<name of the file module that parsed the input>"}
 * All diagnostics go to stderr.  Exit codes: 0 success, 1 conversion
 * failure, 2 bad invocation.
 *
 * Initialization sequence follows gwyddion/thumbnailer/gwyddion-thumbnailer.c,
 * the reference for headless (no display) file loading.
 *
 * License: GPL-2.0-or-later (links Gwyddion libraries).
 */
#include <locale.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <gtk/gtk.h>
#include <libgwyddion/gwyddion.h>
#include <libprocess/gwyprocess.h>
#include <libgwymodule/gwymoduleloader.h>
#include <libgwymodule/gwymodule-file.h>
#include <app/settings.h>

/* Declared in <libgwydgets/gwydgets.h>, which cannot be included here:
 * that umbrella header pulls in gtkglext (gdk/gdkgl.h), whose development
 * files Ubuntu's libgwyddion20-dev does not depend on.  The symbol itself
 * lives in libgwydgets2, which we link anyway. */
void gwy_widgets_type_init(void);

/* Registering modules dlopen()s every file module on the system, and any of
 * them may warn while doing so.  Against a distribution's Gwyddion this is
 * routine rather than a fault: pixmap.so registers png and jpeg itself and
 * also enumerates GdkPixbuf's formats, which in current GdkPixbuf have those
 * loaders built in, so Gwyddion reports
 *
 *     GwyModule-WARNING **: Duplicate function png, keeping only first
 *
 * keeps the first and carries on.  No environment variable reaches it —
 * GDK_PIXBUF_MODULE_FILE only governs loadable modules, not built-in ones —
 * and it lands on stderr on every single run, successful ones included,
 * where gwyddionpy quotes it back to the caller in its error messages.
 *
 * Warnings are therefore discarded for the duration of registration only.
 * Nothing diagnostic is lost: which modules actually registered is exactly
 * what --list-formats reports on stdout, anything at CRITICAL or ERROR level
 * still gets through, and everything emitted once conversion starts is
 * untouched. */
static void
discard_registration_warning(const gchar *domain, GLogLevelFlags level,
                             const gchar *message, gpointer user_data)
{
    (void)user_data;
    if (level & (G_LOG_LEVEL_ERROR | G_LOG_LEVEL_CRITICAL))
        g_log_default_handler(domain, level, message, NULL);
}

static void
init_gwyddion(void)
{
    const gchar *const module_types[] = { "file", NULL };
    GPtrArray *module_dirs;
    GLogFunc previous_handler;
    gchar *p, *q;
    guint i;

    gwy_widgets_type_init();
    /* Some file modules consult settings; missing settings are harmless. */
    gwy_app_settings_load(gwy_app_settings_get_settings_filename(), NULL);

    module_dirs = g_ptr_array_new();
    p = gwy_find_self_dir("modules");
    for (i = 0; module_types[i]; i++)
        g_ptr_array_add(module_dirs, g_build_filename(p, module_types[i], NULL));
    g_free(p);

    q = gwy_get_user_dir();
    for (i = 0; module_types[i]; i++)
        g_ptr_array_add(module_dirs, g_build_filename(q, module_types[i], NULL));

    g_ptr_array_add(module_dirs, NULL);
    previous_handler = g_log_set_default_handler(discard_registration_warning,
                                                 NULL);
    gwy_module_register_modules((const gchar**)module_dirs->pdata);
    g_log_set_default_handler(previous_handler, NULL);

    for (i = 0; module_dirs->pdata[i]; i++)
        g_free(module_dirs->pdata[i]);
    g_ptr_array_free(module_dirs, TRUE);
}

static void
print_json_escaped(const gchar *s)
{
    for (; *s; s++) {
        guchar c = (guchar)*s;
        if (c == '"' || c == '\\')
            printf("\\%c", c);
        else if (c < 0x20)
            printf("\\u%04x", c);
        else
            putchar(c);
    }
}

static void
gather_func_name(gpointer name, gpointer user_data)
{
    g_ptr_array_add((GPtrArray*)user_data, name);
}

static gint
compare_names(gconstpointer a, gconstpointer b)
{
    return strcmp(*(const gchar**)a, *(const gchar**)b);
}

static int
list_formats(void)
{
    GPtrArray *names = g_ptr_array_new();
    guint i;

    gwy_file_func_foreach(gather_func_name, names);
    g_ptr_array_sort(names, compare_names);

    printf("[\n");
    for (i = 0; i < names->len; i++) {
        const gchar *name = (const gchar*)g_ptr_array_index(names, i);
        GwyFileOperationType ops = gwy_file_func_get_operations(name);

        printf("  {\"name\": \"");
        print_json_escaped(name);
        printf("\", \"description\": \"");
        print_json_escaped(gwy_file_func_get_description(name));
        printf("\", \"can_load\": %s, \"can_save\": %s, \"detectable\": %s}%s\n",
               (ops & GWY_FILE_OPERATION_LOAD) ? "true" : "false",
               (ops & (GWY_FILE_OPERATION_SAVE | GWY_FILE_OPERATION_EXPORT))
                   ? "true" : "false",
               gwy_file_func_get_is_detectable(name) ? "true" : "false",
               (i + 1 < names->len) ? "," : "");
    }
    printf("]\n");

    g_ptr_array_free(names, TRUE);
    return 0;
}

static int
convert(const gchar *input, const gchar *output)
{
    GwyContainer *container;
    const gchar *used_module = NULL;
    GError *err = NULL;

    container = gwy_file_load_with_func(input, GWY_RUN_NONINTERACTIVE,
                                        &used_module, &err);
    if (!container) {
        fprintf(stderr, "gwyconvert: cannot load '%s': %s\n",
                input, err ? err->message : "unknown error");
        g_clear_error(&err);
        return 1;
    }

    if (!gwy_file_func_run_save("gwyfile", container, output,
                                GWY_RUN_NONINTERACTIVE, &err)) {
        fprintf(stderr, "gwyconvert: cannot write '%s': %s\n",
                output, err ? err->message : "unknown error");
        g_clear_error(&err);
        g_object_unref(container);
        return 1;
    }
    g_object_unref(container);

    printf("{\"module\": \"");
    print_json_escaped(used_module ? used_module : "");
    printf("\"}\n");
    return 0;
}

int
main(int argc, char *argv[])
{
#ifdef G_OS_WIN32
    /* Windows hands main() its arguments in the process code page, so a path
     * holding anything outside it — "Ångström-messungen" — arrives already
     * mangled and cannot be opened, reported as "Cannot open file for
     * reading: Invalid argument". g_win32_get_command_line() returns the
     * real command line as UTF-8, which is the encoding GLib's file
     * functions and Gwyddion expect on every platform. Freed by exiting. */
    gchar **utf8_argv = g_win32_get_command_line();

    argv = utf8_argv;
    argc = (int)g_strv_length(utf8_argv);
#endif

    /* Initializes GTK type machinery without requiring a display. */
    gtk_parse_args(&argc, &argv);

    /* gtk_parse_args() has just called setlocale(LC_ALL, ""), which adopts
     * the machine's number formatting: the same measurement then reports a
     * duty cycle of "0,881" on a German-configured machine and "0.881" on an
     * English one, and callers reading that as a number get different
     * answers depending on whose computer ran it.
     *
     * gwyddionpy also sets LC_NUMERIC=C in the environment it supplies, but
     * that is a POSIX mechanism: the Microsoft C runtime's setlocale reads
     * the user's OS locale and ignores LC_ALL and LC_NUMERIC entirely, so on
     * Windows no environment can pin this from outside. Pinning it here
     * works the same way on every platform and regardless of how the process
     * was launched. Only the numeric category is touched, so the µm and °C
     * this metadata is full of keep their encoding. */
    setlocale(LC_NUMERIC, "C");

    if (argc == 2 && gwy_strequal(argv[1], "--list-formats")) {
        init_gwyddion();
        return list_formats();
    }
    if (argc == 3 && argv[1][0] != '-') {
        init_gwyddion();
        return convert(argv[1], argv[2]);
    }

    fprintf(stderr,
            "Usage: gwyconvert INPUT OUTPUT.gwy\n"
            "       gwyconvert --list-formats\n");
    return 2;
}
