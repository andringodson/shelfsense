import numpy as np

from generate_data import simulate


def test_simulation_is_consistent():
    stores, skus, sales, demand, stock_end, receipts = simulate(n_stores=4, n_skus=10, days=5, seed=1)
    assert sales.shape == (5 * 24, 4, 10)
    assert (sales <= demand).all() and (stock_end >= 0).all()
    # Stock conservation per hour: previous stock + received - sold = stock at end of hour.
    received = np.zeros_like(sales)
    for h, s, k, qty in receipts:
        received[h, s, k] += qty
    prev = np.vstack([stock_end[:1] + sales[:1] - received[:1], stock_end[:-1]])
    assert (prev + received - sales == stock_end).all()
    # Censoring only happens on empty shelves - the property the analytics rely on.
    assert (stock_end[sales < demand] == 0).all()
    assert (sales < demand).any(), "simulation should produce some stock-outs"


def test_deterministic():
    a, b = simulate(2, 5, 2, seed=3), simulate(2, 5, 2, seed=3)
    assert (a[2] == b[2]).all()
