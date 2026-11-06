

def test_a_copy_of_the_answer_is_dropped_before_training():
    import pandas as pd
    from app.services.data.features import leaky_columns, prepare_features
    df = pd.DataFrame({"a": [1, 2, 1, 2, 1, 2], "left": [0, 1, 0, 1, 0, 1], "cancelled_flag": [0, 1, 0, 1, 0, 1], "near": [0, 1, 0, 1, 0, 0]})
    assert leaky_columns(df, "left") == ["cancelled_flag"]       # an exact copy only; a near copy is the baseline check's job
    assert list(prepare_features(df, "left").columns) == ["a", "left", "near"]
