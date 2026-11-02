"""Deterministic grouping helpers for generation experiments."""
import hashlib
import unicodedata


def person_key(name):
    normalized=unicodedata.normalize('NFKD',str(name).casefold().replace('_',' '))
    return ''.join(c for c in normalized if c.isalnum())


def group_split(group, seed=20261031):
    value=int(hashlib.sha256(f'{seed}:{group}'.encode()).hexdigest()[:16],16)/2**64
    return 'train' if value<.70 else 'val' if value<.85 else 'test'


class UnionFind:
    def __init__(self, groups):
        self.parent={g:g for g in groups}

    def find(self, group):
        root=group
        while self.parent[root]!=root:
            root=self.parent[root]
        while group!=root:
            previous=group
            group=self.parent[group]
            self.parent[previous]=root
        return root

    def union(self, a, b):
        a,b=self.find(a),self.find(b)
        if a!=b:self.parent[max(a,b)]=min(a,b)


def component_split(rows):
    """Never pretend removing old training rows erases checkpoint pretraining exposure."""
    if any(row.get('pretrained_train') for row in rows):
        return 'train'
    roles={row['split'] for row in rows}
    return 'test' if 'test' in roles else 'val' if 'val' in roles else 'train'
