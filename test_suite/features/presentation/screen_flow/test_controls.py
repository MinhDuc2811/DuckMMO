from streamlit.testing.v1 import AppTest


def test_presentation_controls_return_independent_style_and_audio_choices():
    def screen():
        import streamlit as st

        from ui.components.presentation import music_controls, visual_controls

        catalog = {
            "presets": [{"id": "comic", "name": "Comic"}],
            "tracks": [{"id": "ambient", "name": "Nền êm"}],
        }

        def request(*args, **kwargs):
            return catalog

        visual, catalog = visual_controls(request, "test", {})
        music, _, _ = music_controls(catalog, [], {}, "test")
        st.json({"visual": visual, "music": music})

    app = AppTest.from_function(screen).run()
    assert not app.exception
    app.selectbox[0].select("comic").run()
    app.radio[0].set_value("library").run()
    assert not app.exception
    import json

    result = json.loads(app.json[0].value)
    assert result["visual"]["preset"] == "comic"
    assert result["music"]["track"] == "ambient"
    app.checkbox[1].uncheck().run()
    assert json.loads(app.json[0].value)["music"]["ducking"] is False
