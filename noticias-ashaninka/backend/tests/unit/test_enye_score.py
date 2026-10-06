import csv

from eval.listening.enye_ab.score import binom_two_sided, read_answers, score


def test_binomial():
    assert binom_two_sided(0, 0) == 1.0
    assert binom_two_sided(5, 10) == 1.0
    assert round(binom_two_sided(0, 10), 4) == 0.002


def test_score_counts_controls_pairs_and_rates(tmp_path):
    key = tmp_path / "clave.csv"
    rows = [
        {"par": 1, "palabra": "x", "posicion": "inicial", "A": "H1", "B": "H3", "control": False},
        {"par": 2, "palabra": "y", "posicion": "interna", "A": "H3", "B": "H1", "control": False},
        {"par": 3, "palabra": "z", "posicion": "interna", "A": "H2", "B": "H3", "control": False},
        {"par": 4, "palabra": "x", "posicion": "inicial", "A": "H1", "B": "H1", "control": True},
    ]
    with open(key, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    answers = tmp_path / "resp.csv"
    answers.write_text(
        "par,respuesta,comentario\n1,B,\n2,A,\n3,igual,\n4,igual,\n", encoding="utf-8"
    )
    res = score(read_answers(answers), key)
    assert res["pares_respondidos"] == 4
    assert res["controles"] == {"total": 1, "marcados_igual": 1, "pct": 100.0}
    assert res["por_par"]["H1-H3"]["H3"] == 2 and res["por_par"]["H2-H3"]["empates"] == 1
    assert res["tasa_victoria"]["total"]["H3"] == 1.0
