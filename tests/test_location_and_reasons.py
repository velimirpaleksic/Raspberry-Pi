import unittest

from project.core import config
from project.core.location_rules import municipality_for_place, normalize_location_key
from project.gui.ui_components import paginate_values
from project.gui.screens.c_form import FormScreen


EXPECTED_REASONS = [
    "Омладинску задругу",
    "Отварање рачуна у банци",
    "Здравствено осигурање",
    "Превоз",
    "Стипендију брата/сестре",
    "Новчана средства за уџбенике",
    "Давање изјаве у полицији",
    "Конкурс полицијска академија",
    "Регулисање уписнине",
    "Алиментација",
    "Регулисање породичне пензије",
    "Помоћ за породице 4+",
]


class LocationRulesTests(unittest.TestCase):
    def test_location_key_normalizes_case_and_whitespace(self):
        self.assertEqual(normalize_location_key("  KaSInDo   "), "kasindo")
        self.assertEqual(normalize_location_key(" КАСИНДО  "), "касиндо")

    def test_kasindo_maps_in_latin_and_cyrillic(self):
        for value in ("Kasindo", "  KASINDO ", "Касиндо", "  касиндо  "):
            with self.subTest(value=value):
                self.assertEqual(municipality_for_place(value), "Источна Илиџа")

    def test_unknown_place_leaves_municipality_manual(self):
        self.assertEqual(municipality_for_place("Сарајево"), "")

    def test_form_rule_autofills_known_place_and_preserves_unknown_manual_value(self):
        class Entry:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        place = Entry("  kasindo  ")
        municipality = Entry("")
        fake_form = type("FakeForm", (), {})()
        fake_form._suppress_field_events = False
        fake_form._auto_opstina_value = ""
        fake_form.mjesto_entry = place
        fake_form.opstina_entry = municipality
        fake_form._normalize_title = lambda value: " ".join(
            part[:1].upper() + part[1:].lower() for part in str(value or "").strip().split()
        )
        fake_form._set_entry_text = lambda entry, value, **_kwargs: setattr(entry, "value", value)

        self.assertEqual(FormScreen._apply_mapped_municipality(fake_form), "Источна Илиџа")
        self.assertEqual(municipality.value, "Источна Илиџа")

        place.value = "Сарајево"
        municipality.value = "Нови Град"
        fake_form._auto_opstina_value = ""
        self.assertEqual(FormScreen._apply_mapped_municipality(fake_form), "")
        self.assertEqual(municipality.value, "Нови Град")

    def test_final_form_rule_overrides_known_place_with_canonical_cyrillic_value(self):
        class Entry:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        fake_form = type("FakeForm", (), {})()
        fake_form._suppress_field_events = False
        fake_form._auto_opstina_value = ""
        fake_form.mjesto_entry = Entry("Касиндо")
        fake_form.opstina_entry = Entry("Ручно унесено")
        fake_form._normalize_title = lambda value: " ".join(
            part[:1].upper() + part[1:].lower() for part in str(value or "").strip().split()
        )
        fake_form._set_entry_text = lambda entry, value, **_kwargs: setattr(entry, "value", value)
        FormScreen._apply_mapped_municipality(fake_form, force=True)
        self.assertEqual(fake_form.opstina_entry.value, "Источна Илиџа")


class ReasonPickerTests(unittest.TestCase):
    def test_reasons_have_requested_order_and_only_requested_items(self):
        self.assertEqual(config.RAZLOZI, EXPECTED_REASONS)

    def test_reason_pages_are_deterministic_and_clamped(self):
        first, page, count = paginate_values(config.RAZLOZI, 0, 5)
        second, second_page, second_count = paginate_values(config.RAZLOZI, 1, 5)
        third, third_page, third_count = paginate_values(config.RAZLOZI, 2, 5)
        past_end, clamped, _ = paginate_values(config.RAZLOZI, 99, 5)
        self.assertEqual(first, EXPECTED_REASONS[:5])
        self.assertEqual(second, EXPECTED_REASONS[5:10])
        self.assertEqual(third, EXPECTED_REASONS[10:])
        self.assertEqual((page, count), (0, 3))
        self.assertEqual((second_page, second_count), (1, 3))
        self.assertEqual((third_page, third_count), (2, 3))
        self.assertEqual((past_end, clamped), (EXPECTED_REASONS[10:], 2))


if __name__ == "__main__":
    unittest.main()
