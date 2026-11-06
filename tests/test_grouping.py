from snaplist.grouping import pre_cluster, group_photos, merge_into


def test_pre_cluster_buckets_by_color():
    groups = pre_cluster([])
    assert groups == []


def test_merge_into_adds_disjoint_and_merges_overlap():
    merged: list[list[int]] = []
    merge_into(merged, [1, 2])
    merge_into(merged, [3, 4])
    merge_into(merged, [2, 3])
    flat = {x for g in merged for x in g}
    assert flat == {1, 2, 3, 4}


async def test_group_photos_returns_groups(provider, sample_photos):
    groups = await group_photos(provider, sample_photos)
    assert len(groups) >= 1
    total = sum(len(g.indexes) for g in groups)
    assert total == len(sample_photos)


async def test_group_photos_maps_chunk_local_indexes_and_keeps_all(provider, tmp_path):
    from PIL import Image
    paths = []
    for i in range(30):
        p = tmp_path / f"p{i}.png"
        Image.new("RGB", (32, 32), (i, i, i)).save(p)
        paths.append(str(p))
    groups = await group_photos(provider, paths, max_per_chunk=12)
    flat = sorted(x for g in groups for x in g.indexes)
    assert flat == list(range(30))  # no photo lost after the first chunk
