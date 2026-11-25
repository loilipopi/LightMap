from lightmap.overlay_layout import OverlayLayout
from lightmap.preferences import AppPreferences, AudioTuning, SmoothingTimes, load_preferences, save_preferences


def test_preferences_round_trip_and_replace_previous_file(tmp_path):
    file = tmp_path / "LightMap" / "settings.json"
    assert load_preferences(file) == AppPreferences()
    preferences = AppPreferences(
        palette=str(tmp_path / "my image.png"), smoothing=False, overlay_enabled=True,
        layout=OverlayLayout("circle", size=65, x_percent=80, y_percent=25, opacity=72),
        audio=AudioTuning(-42, (28, 75, 119), 200, 0, 75),
    )
    save_preferences(file, AppPreferences(palette="ocean"))
    save_preferences(file, preferences)
    assert load_preferences(file) == preferences
    assert list(file.parent.iterdir()) == [file]


def test_preferences_restore_rotated_polygon_and_independent_fades(tmp_path):
    path = tmp_path / "settings.json"
    prefs = AppPreferences(
        layout=OverlayLayout("triangle", width=149, height=87, rotation=-35),
        smoothing_times=SmoothingTimes(0, 240),
    )
    save_preferences(path, prefs)
    assert load_preferences(path) == prefs
    path.write_text('{"smoothing": false, "layout": {"shape": "circle", "size": 63}}')
    assert load_preferences(path) == AppPreferences(
        smoothing=False, layout=OverlayLayout("circle", size=63)
    )


def test_invalid_settings_recover_without_discarding_valid_entries(tmp_path):
    file = tmp_path / "settings.json"
    file.write_text('{"palette": "ember", "overlay_enabled": true, "smoothing": 1, '
                    '"audio": {"quiet_colour": [0, 13, 300]}, "layout": {"shape": "star"}}')
    assert load_preferences(file) == AppPreferences(palette="ember", overlay_enabled=True)
    file.write_text("{")
    assert load_preferences(file) == AppPreferences()
