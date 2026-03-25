from longyin_mod_installer.services.keyvalues import parse_keyvalues


def test_parse_libraryfolders_new_format() -> None:
    parsed = parse_keyvalues(
        """
        "libraryfolders"
        {
            "0"
            {
                "path" "D:\\\\soft\\\\steam"
            }
            "1"
            {
                "path" "E:\\\\SteamLibrary"
            }
        }
        """
    )

    libraryfolders = parsed["libraryfolders"]
    assert isinstance(libraryfolders, dict)
    assert libraryfolders["1"]["path"] == "E:\\SteamLibrary"


def test_parse_manifest() -> None:
    parsed = parse_keyvalues(
        """
        "AppState"
        {
            "appid" "3202030"
            "name" "龙胤立志传"
            "installdir" "LongYinLiZhiZhuan"
        }
        """
    )

    app_state = parsed["AppState"]
    assert isinstance(app_state, dict)
    assert app_state["appid"] == "3202030"
    assert app_state["installdir"] == "LongYinLiZhiZhuan"
