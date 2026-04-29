import unittest

from app.seed import (
    ABSENCE_MESSAGES,
    PARENT_NAMES,
    STUDENT_NAMES,
    SUBJECT_NAMES,
    TEACHER_NAMES,
    build_demo_blueprint,
    build_mark_score,
)


class DemoSeedBlueprintTests(unittest.TestCase):
    def test_blueprint_contains_expected_school_structure(self):
        blueprint = build_demo_blueprint()

        self.assertEqual(blueprint["school"]["name"], "Sunrise High School")
        self.assertEqual(blueprint["class_names"][0], "Grade 1")
        self.assertEqual(blueprint["class_names"][-1], "Grade 10")
        self.assertEqual(len(blueprint["class_names"]), 10)
        self.assertEqual(blueprint["subjects"], SUBJECT_NAMES)
        self.assertEqual(len(blueprint["students_per_class"]), 10)
        self.assertEqual(len(blueprint["teachers"]["class_teachers"]), 10)
        self.assertEqual(len(blueprint["teachers"]["subject_teachers"]), 40)

    def test_seed_data_catalogs_are_realistic_and_complete(self):
        self.assertGreaterEqual(len(STUDENT_NAMES), 20)
        self.assertGreaterEqual(len(PARENT_NAMES), 20)
        self.assertGreaterEqual(len(TEACHER_NAMES), 20)
        self.assertGreaterEqual(len(ABSENCE_MESSAGES), 3)

    def test_mark_scores_stay_in_demo_range(self):
        scores = [build_mark_score(student_index=3, subject_index=idx, class_index=2) for idx in range(4)]

        for score in scores:
            self.assertGreaterEqual(score, 60)
            self.assertLessEqual(score, 100)


if __name__ == "__main__":
    unittest.main()
