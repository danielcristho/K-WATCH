"""BENIGN_LABELS indexes the trained class order, so a stale value must fail loudly."""

from core.modelstore import _check_benign_labels

# The order the models were trained in; classes 0-4 are the attacks.
NAMES = ["Botnet", "Cryptominer", "Trojan-Agent", "Cloud Attack", "Brute-Force",
         "Data-Caching", "Database", "Redis", "Web-Serving"]

# Each of these shipped or could ship, and each is wrong in a way nothing else catches.
BAD = {
    "class 9 does not exist, and Data-Caching is benign": {6, 7, 8, 9},
    "nothing benign, so every pod alerts":                 set(),
    "everything benign, so nothing ever alerts":           set(range(9)),
}


def test_the_deployed_value_passes():
    _check_benign_labels(NAMES, {5, 6, 7, 8})


def test_a_stale_value_raises():
    for why, labels in BAD.items():
        try:
            _check_benign_labels(NAMES, labels)
        except ValueError:
            continue
        raise AssertionError(f"accepted {sorted(labels)}: {why}")


if __name__ == "__main__":
    test_the_deployed_value_passes()
    test_a_stale_value_raises()
    print(f"ok: {len(NAMES)} classes, deployed value accepted, {len(BAD)} stale values rejected")
