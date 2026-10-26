"""Source-balanced weighting and known-vs-unknown local supervision must stay correct."""
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image
import torch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference_run'))
from local_edit_supervision import LocalEditImages,LocalEditNetwork,self_blend
from train_generation import balanced_source_weights,audit


class TrainingTests(unittest.TestCase):
    def test_shared_prompt_does_not_distort_source_balance(self):
        rows=[dict(group='shared',label='0',source='realA',method='real'),
              dict(group='shared',label='1',source='fakeA',method='genA'),
              dict(group='shared',label='1',source='fakeA',method='genA'),
              dict(group='other',label='1',source='fakeB',method='genB')]
        weights=balanced_source_weights(rows)
        self.assertAlmostEqual(weights[0],.5)
        self.assertAlmostEqual(sum(weights[1:3]),.25)
        self.assertAlmostEqual(weights[3],.25)

    def test_external_generator_cannot_enter_tuning(self):
        row=dict(sample_id='forbidden',method='gpt-image-2',split='train',label='1')
        with self.assertRaisesRegex(ValueError,'Locked external generator'):
            audit([row],allow_sd35_training=True,allow_openfake=True)

    def test_controlled_mask_is_nonempty_and_reproducible(self):
        image=Image.fromarray(np.random.default_rng(7).integers(0,256,(128,128,3),dtype=np.uint8))
        first,mask=self_blend(image,np.random.default_rng(100))
        second,same=self_blend(image,np.random.default_rng(100))
        np.testing.assert_array_equal(mask,same)
        np.testing.assert_array_equal(np.asarray(first),np.asarray(second))
        self.assertGreater(mask.max(),.9)
        self.assertGreater(mask.mean(),.01)
        self.assertLess(mask.mean(),.5)
        self.assertFalse(np.array_equal(np.asarray(first),np.asarray(image)))

    def test_unknown_fake_masks_are_not_used_as_true_segmentation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'face.png';Image.new('RGB',(256,256),'gray').save(path)
            rows=[dict(path=str(path),label='1'),dict(path=str(path),label='0'),dict(path=str(path),label='1',synthetic=True)]
            dataset=LocalEditImages(rows)
            self.assertEqual(dataset[0][3],0)
            self.assertEqual(dataset[1][3],1)
            self.assertEqual(dataset[2][3],1)

    def test_classifier_forward_matches_exported_backbone_path(self):
        torch.set_num_threads(2)
        model=LocalEditNetwork().eval()
        images=torch.zeros(2,3,224,224)
        with torch.inference_mode():
            logits,masks=model(images)
            exported=model.head(model.encoder(images)).flatten()
        torch.testing.assert_close(logits,exported)
        self.assertEqual(tuple(masks.shape),(2,1,14,14))


if __name__=='__main__':unittest.main()
