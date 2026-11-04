"""Coverage bounds, short event sampling, spatial associations, and quarantine integrity."""
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reference_run'))
from audit_near_duplicates import near_pairs
from quarantine_similar_groups import quarantine
from video_analysis import coarse_targets, refinement_targets, spatial_tracks, review_windows
from video_analysis import temporal_alert_score,calibrated_windows
from calibrate_video_review import choose_threshold


class VideoTests(unittest.TestCase):
    def test_more_frames_cannot_override_empirical_false_alert_budget(self):
        values=[i/140 for i in range(140)]
        threshold=choose_threshold(values,.01)
        self.assertLessEqual(sum(p>=threshold for p in values),1)
        tied=choose_threshold([.9]*140,.05)
        self.assertEqual(sum(p>=tied for p in [.9]*140),0)

    def test_temporal_statistic_needs_two_observations_of_same_track(self):
        result=dict(fps=25,observations=[dict(frame_index=0,faces=[dict(track_id=1,score=.99)]),
                                         dict(frame_index=1,faces=[dict(track_id=2,score=.99)])])
        self.assertIsNone(temporal_alert_score(result))
        result['observations'][1]['faces'][0]['track_id']=1
        self.assertAlmostEqual(temporal_alert_score(result),.99)

    def test_review_windows_use_calibrated_pairs_and_clip_to_duration(self):
        pairs=[dict(first_frame=0,last_frame=5,track_id=1,score=.99),
               dict(first_frame=90,last_frame=99,track_id=1,score=.1)]
        windows=calibrated_windows(pairs,.98,25,4)
        self.assertEqual(len(windows),1)
        self.assertEqual(windows[0]['evidence_frames'],[0,5])
        self.assertGreaterEqual(windows[0]['start_seconds'],0)
        self.assertLessEqual(windows[0]['end_seconds'],4)
    def test_budget_preserves_legacy_coverage_and_endpoints(self):
        for count, fps in [(1, 25), (12, 25), (300, 25), (25000, 25), (1000, None)]:
            targets, legacy = coarse_targets(count, fps)
            self.assertLessEqual(len(targets), 96)
            self.assertEqual((targets[0], targets[-1]), (0, count - 1))
            self.assertTrue(legacy <= set(targets))
            self.assertEqual(len(targets), len(set(targets)))
            self.assertTrue(all(0 <= i < count for i in targets))

    def test_short_event_outside_16_samples_can_receive_coverage(self):
        targets, legacy = coarse_targets(300, 25)
        extra = sorted(set(targets) - legacy)
        self.assertTrue(extra)
        # A 3-frame event around this extra position was absent from all original samples.
        center = next(i for i in extra if all(abs(i - old) > 2 for old in legacy))
        self.assertTrue(any(center - 1 <= i <= center + 1 for i in targets))
        self.assertFalse(any(center - 1 <= i <= center + 1 for i in legacy))

    def test_refinement_is_bounded_near_candidates_and_never_duplicates(self):
        observations = [dict(frame_index=i, faces=[dict(score=.9 if i == 50 else .1)]) for i in range(0, 101, 10)]
        extra = refinement_targets(101, 25, observations, .6, budget=4)
        self.assertTrue(extra)
        self.assertLessEqual(len(extra), 4)
        self.assertTrue(all(40 < i < 60 and i not in range(0, 101, 10) for i in extra))

    def test_tracks_do_not_merge_two_people_in_one_frame(self):
        observations = [dict(frame_index=i, faces=[dict(bbox=[10+i, 10, 40+i, 40], score=.9),
                                                  dict(bbox=[100+i, 10, 130+i, 40], score=.1)]) for i in (0, 1)]
        spatial_tracks(observations, 25)
        self.assertEqual([f['track_id'] for f in observations[0]['faces']], [1, 2])
        self.assertEqual([f['track_id'] for f in observations[1]['faces']], [1, 2])
        windows = review_windows(observations, 25, .6)
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]['track_ids'], [1])
        self.assertEqual(windows[0]['evidence_frames'], [0, 1])


class AuditTests(unittest.TestCase):
    def test_candidate_index_does_not_miss_near_hashes(self):
        rng = random.Random(20)
        values = [rng.getrandbits(64) for _ in range(100)]
        values += [v ^ 3 ^ (1 << 40) for v in values[:10]]
        for distance in (0, 3, 6):
            actual = {(i, j, d) for i, j, d in near_pairs(values, distance)}
            expected = {(i, j, (a ^ b).bit_count()) for i, a in enumerate(values)
                        for j, b in enumerate(values) if i < j and (a ^ b).bit_count() <= distance}
            self.assertEqual(actual, expected)

    def test_quarantine_removes_whole_related_group_preserving_test(self):
        rows = [dict(sample_id='a', group='train-person', split='train'),
                dict(sample_id='a2', group='train-person', split='train'),
                dict(sample_id='b', group='val-person', split='val'),
                dict(sample_id='c', group='test-person', split='test'),
                dict(sample_id='d', group='unrelated', split='train')]
        pairs = [dict(left_id='a', right_id='b'), dict(left_id='b', right_id='c')]
        kept, removed = quarantine(rows, pairs)
        self.assertEqual({r['sample_id'] for r in kept}, {'c', 'd'})
        self.assertEqual({r['sample_id'] for r in removed}, {'a', 'a2', 'b'})


if __name__ == '__main__':
    unittest.main()
