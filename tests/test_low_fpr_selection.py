"""FPR budgets, score ties and validation-only boundaries must survive ranking."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from faceguard.generation_selection import select_operating_point, operating_rank


def rows(labels, methods=None):
    return [dict(sample_id=str(i),split='val',label=str(label),source='real-source' if not label else 'fake-source',
                 group=str(i),method=('real' if not label else 'gpt-image-1') if methods is None else methods[i])
            for i,label in enumerate(labels)]


class LowFprSelectionTests(unittest.TestCase):
    def test_tied_negatives_cannot_spend_more_than_integer_false_positive_budget(self):
        result=select_operating_point(rows([0,0,0,0,1,1]),[.9,.8,.8,.1,.95,.85],.25)
        self.assertTrue(result['budget_met'])
        self.assertEqual(result['false_positives'],1)
        self.assertEqual(result['per_generator']['gpt-image-1']['detected'],2)

    def test_zero_budget_can_reject_all_when_negative_score_is_one(self):
        result=select_operating_point(rows([0,1]),[1.,1.],0.)
        self.assertGreater(result['threshold'],1.)
        self.assertEqual(result['false_positives'],0)
        self.assertEqual(result['focus_macro_recall'],0.)

    def test_test_rows_missing_focus_and_nonfinite_scores_are_rejected(self):
        data=rows([0,1])
        with self.assertRaises(ValueError):select_operating_point(data,[.1,np.nan])
        with self.assertRaises(ValueError):select_operating_point(data,[.1,.9],focus_methods=['gpt-image-2'])
        data[1]['split']='test'
        with self.assertRaisesRegex(ValueError,'validation rows only'):select_operating_point(data,[.1,.9])

    def test_prompt_copies_do_not_amplify_focus_group_recall(self):
        data=rows([0,1,1,1]);data[1]['group']=data[2]['group']='same-prompt'
        result=select_operating_point(data,[.5,.9,.9,.1],0.)
        self.assertAlmostEqual(result['per_generator']['gpt-image-1']['recall'],2/3)
        self.assertEqual(result['focus_macro_recall'],.5)

    def test_fpr_operating_recall_takes_priority_over_auc(self):
        first=select_operating_point(rows([0,1,1]),[.5,.8,.9],0.)
        second=select_operating_point(rows([0,1,1]),[.5,.8,.1],0.)
        self.assertGreater(operating_rank(first,.8),operating_rank(second,.99))

    def test_cached_prediction_cannot_change_validation_labels_or_groups(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
        from benchmark_generation_operating_points import matched_scores
        data=rows([0,1]);predictions=[dict(r,score=.2) for r in data]
        predictions[0]['label']='1'
        with self.assertRaisesRegex(ValueError,'labels/source'):matched_scores(data,predictions)
        predictions[0]['label']='0';predictions[0]['group']='different'
        with self.assertRaisesRegex(ValueError,'group differs'):matched_scores(data,predictions)

    def test_duplicate_cache_ids_are_not_silently_overwritten(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
        from benchmark_generation_operating_points import matched_scores
        data=rows([0,1]);predictions=[dict(data[0],score=.2)]*2
        with self.assertRaisesRegex(ValueError,'Duplicate'):matched_scores(data,predictions)


if __name__=='__main__':unittest.main()
