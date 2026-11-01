"""Overview emphasis must follow decisions without implying authenticity."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from faceguard.detection import task_state, task_summary


class DetectionPresentationTests(unittest.TestCase):
    def test_errors_missing_tasks_and_no_face_are_not_clear(self):
        self.assertEqual(task_state({}, 'generation'), 'idle')
        for result in [dict(errors={'generation': 'failed'}),
                       dict(task='whole_face_generation', decision='no_face'),
                       dict(results={'manipulation': {'decision': 'no_manipulation_detected'}})]:
            self.assertEqual(task_state(result, 'generation'), 'unavailable')

    def test_any_suspicious_face_receives_attention(self):
        result = dict(results={'generation': dict(decision='multiple_face_results', face_results=[
            dict(decision='no_generation_detected'), dict(decision='suspected_generation')])})
        self.assertEqual(task_state(result, 'generation'), 'attention')
        self.assertEqual(task_state(dict(task='whole_face_generation', decision='no_generation_detected'), 'generation'), 'clear')

    def test_video_review_alerts_remain_visible_despite_negative_baseline(self):
        result = dict(media_type='video', legacy_baseline=dict(decision='no_manipulation_detected'),
                      temporal_review=dict(decision='review_alerts'))
        self.assertEqual(task_state(result, 'generation'), 'unavailable')
        self.assertEqual(task_state(result, 'manipulation'), 'attention')
        self.assertEqual(task_summary(result, 'manipulation'), '局部片段需复核')
        result['temporal_review']['decision'] = 'no_review_alerts'
        self.assertEqual(task_state(result, 'manipulation'), 'clear')


if __name__ == '__main__':
    unittest.main()
