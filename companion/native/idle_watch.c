/* Read-only input-idle transitions. No key events, input capture or injection. */
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <unistd.h>
#include <wayland-client.h>
#include "ext-idle-notify-v1-client-protocol.h"

static struct wl_seat *seat;
static struct ext_idle_notifier_v1 *notifier;
static unsigned notifier_version;
static void global(void *data, struct wl_registry *registry, uint32_t name, const char *interface, uint32_t version) {
    (void)data;
    if (!strcmp(interface, "wl_seat") && !seat)
        seat = wl_registry_bind(registry, name, &wl_seat_interface, 1);
    if (!strcmp(interface, "ext_idle_notifier_v1") && !notifier) {
        notifier_version = version >= 2 ? 2 : 1;
        notifier = wl_registry_bind(registry, name, &ext_idle_notifier_v1_interface, notifier_version);
    }
}
static void removed(void *data, struct wl_registry *registry, uint32_t name) { (void)data; (void)registry; (void)name; }
static const struct wl_registry_listener registry_listener = {global, removed};
static void idled(void *data, struct ext_idle_notification_v1 *notification) { (void)data; (void)notification; puts("idle"); fflush(stdout); }
static void resumed(void *data, struct ext_idle_notification_v1 *notification) { (void)data; (void)notification; puts("active"); fflush(stdout); }
static const struct ext_idle_notification_v1_listener idle_listener = {idled, resumed};
int main(int argc, char **argv) {
    if (argc != 2) return 125;
    pid_t owner = (pid_t)strtol(argv[1], NULL, 10);
    if (owner <= 1 || getppid() != owner || prctl(PR_SET_PDEATHSIG, SIGTERM) || getppid() != owner) return 125;
    struct wl_display *display = wl_display_connect(NULL);
    if (!display) return 1;
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);
    if (wl_display_roundtrip(display) < 0 || !seat || !notifier || notifier_version < 2) return 2;
    struct ext_idle_notification_v1 *notification = ext_idle_notifier_v1_get_input_idle_notification(notifier, 10000, seat);
    ext_idle_notification_v1_add_listener(notification, &idle_listener, NULL);
    puts("active"); fflush(stdout);
    while (1) {
        if (wl_display_dispatch(display) < 0) break;
    }
    return 1;
}
