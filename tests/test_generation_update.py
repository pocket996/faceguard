"""Identity isolation and inherited checkpoint exposure must survive a new split."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'reference_run'))
from faceguard.training_protocol import person_key,group_split,UnionFind,component_split
from train_generation import audit,validate_generation_initialization


class GenerationUpdateTests(unittest.TestCase):
    def test_named_sources_and_derived_versions_form_one_transitive_component(self):
        self.assertEqual(person_key('René_Test'),person_key('Rene Test'))
        groups=UnionFind(['lfw_person','dff_real','dff_generated','jpeg_copy'])
        groups.union('lfw_person','dff_real');groups.union('dff_real','dff_generated');groups.union('jpeg_copy','dff_generated')
        self.assertEqual(len({groups.find(key) for key in groups.parent}),1)

    def test_removed_old_training_row_still_disqualifies_connected_validation_pixels(self):
        rows=[dict(split='train',ghost=True,pretrained_train=True),dict(split='val',ghost=False,pretrained_train=False)]
        self.assertEqual(component_split(rows),'train')
        self.assertNotEqual(component_split(rows),rows[1]['split'])

    def test_without_checkpoint_exposure_locked_test_has_priority(self):
        self.assertEqual(component_split([dict(split='train'),dict(split='test')]),'test')
        self.assertEqual(group_split('person:sample'),group_split('person:sample'))

    def test_new_generator_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.jpg';path.write_bytes(b'fixture')
            rows=[dict(sample_id=f'{split}-{label}',path=str(path),group=f'{split}-{label}',split=split,
                       label=label,method='SD15' if label=='1' else 'real',pixel_sha256=f'{split}-{label}')
                  for split in ('train','val','test') for label in ('0','1')]
            with self.assertRaisesRegex(ValueError,'Unknown method'):audit(rows)
            audit(rows,allow_dff=True)

    def test_manipulation_or_wrong_preprocessing_checkpoint_cannot_initialize_generation(self):
        for state in (dict(task='face_manipulation'),dict(task='whole_face_generation',preprocessing='manipulation256')):
            with self.assertRaises(ValueError):validate_generation_initialization(state)
        state=dict(task='whole_face_generation',preprocessing='generation128_jpeg90',yunet_sha256='fixture')
        with patch('train_generation.digest',return_value='fixture'):validate_generation_initialization(state)


if __name__=='__main__':unittest.main()
