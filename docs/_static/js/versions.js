/* Fills the version menu that docs/_templates/versions.html leaves empty.
 *
 * The published site keeps one directory per version next to a versions.json listing them, so
 * a page built months ago still offers every version released since: the menu is the site's,
 * not the build's. A build that is not sitting in such a directory - a local one, a pull
 * request one - fails to fetch that file and leaves the menu hidden, which is the honest
 * outcome, since in that case there is nothing to switch to.
 */
(function () {
    "use strict";

    function fill(box, root, index) {
        var here = decodeURI(window.location.href);
        var slot = here.slice(root.href.length).split("/")[0];
        var versions = index.versions || [];

        // The directory the current page is being served from is the version it belongs to.
        // Falls back to the newest release, for the redirect at the root of the site.
        var current = versions.indexOf(slot) === -1 ? index.stable : slot;

        box.querySelector("[data-ddd-current]").textContent = current;

        var list = box.querySelector("[data-ddd-versions]");
        versions.forEach(function (name) {
            var link = document.createElement("a");
            // The root of the other version rather than this same page within it: a page that
            // exists here need not exist there, and a menu that offers 404s is worse than one
            // that costs a click.
            link.href = new URL(encodeURI(name) + "/", root).href;
            link.textContent = name === index.stable ? name + " (stable)" : name;
            if (name === current) {
                link.setAttribute("aria-current", "true");
            }
            list.appendChild(link);
            list.appendChild(document.createElement("br"));
        });

        box.hidden = false;
    }

    // The menu is included at the end of the body and this script from the head, so it waits
    // for the document - but only if the document is still coming. Sphinx emits a plain
    // script tag today; were it ever to emit an async one, the event would already have been
    // fired by the time this ran and a menu that only ever listens would never appear.
    function ready(run) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", run);
        } else {
            run();
        }
    }

    ready(function () {
        var box = document.querySelector(".rst-versions[data-root]");
        if (!box) {
            return;
        }

        var root = new URL(box.getAttribute("data-root"), window.location.href);
        fetch(new URL("versions.json", root).href)
            .then(function (response) {
                return response.ok ? response.json() : Promise.reject(response.status);
            })
            .then(function (index) {
                fill(box, root, index);
            })
            .catch(function () {
                /* Not a published build, so there are no other versions to point at. */
            });
    });
})();
