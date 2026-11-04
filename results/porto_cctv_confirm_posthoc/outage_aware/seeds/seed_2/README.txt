POST-HOC (not pre-registered). '<predictor>_oa' = outage-aware predictor, a separate method added
after the confirmation run: p(c'|src) + p(off|src) p(c'|off), delay by convolution, ONE STEP ONLY
(a second offline site after `off` is not propagated). Thresholds/predictor are not refitted.
cost_over_oracle: against the same predictor's post-hoc oracle; cost_over_base_oracle: against the
base predictor's oracle (common yardstick).
