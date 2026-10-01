"""Optional installed application extensions, independent of language parsers."""
from importlib.metadata import entry_points


def init_app_plugins(app):
    """Installed plugins own their routes/assets and return optional menu links."""
    navigation = []
    available = entry_points()
    entries = (
        available.select(group="lute.plugin.app")
        if hasattr(available, "select")
        else available.get("lute.plugin.app", [])  # pylint: disable=no-member
    )
    for entry in entries:
        try:
            links = entry.load()(app) or []
            navigation.extend(links)
        except Exception:  # A broken optional workspace must not break the reader.
            app.logger.exception(
                "Application plugin %s could not initialize", entry.name
            )
    app.context_processor(lambda: {"plugin_navigation": navigation})
