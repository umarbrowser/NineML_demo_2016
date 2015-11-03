# encoding: utf-8
"""
Plot colour plots of spike train statistics as a function of
the parameters g and eta for the Brunel (2000) model

"""

from __future__ import division, print_function
import os
import argparse
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from quantities import Quantity, ms
from neo import get_io
from elephant.statistics import mean_firing_rate, cv, isi
from elephant.conversion import BinnedSpikeTrain
from elephant.spike_train_correlation import corrcoef
import pandas
from joblib import Parallel, delayed


parser = argparse.ArgumentParser()
parser.add_argument("directory",
                    help="directory containing data generated by running sweep.py")
config = parser.parse_args()

results_dir = config.directory

statistics_file = os.path.join(results_dir, "statistics.csv")


def spike_statistics(idx, row):
    print(idx)
    results = {}

    # read spike trains from file
    io = get_io(row["output_file"])
    data_block = io.read()[0]
    spiketrains = data_block.segments[0].spiketrains

    # calculate mean firing rate
    results["spike_counts"] = sum(st.size for st in spiketrains)
    rates = [mean_firing_rate(st) for st in spiketrains]
    results["firing_rate"] = Quantity(rates, units=rates[0].units).rescale("1/s").mean()

    # calculate coefficient of variation of the inter-spike interval
    cvs = [cv(isi(st)) for st in spiketrains if st.size > 1]
    if len(cvs) > 0:
        results["cv_isi"] = sum(cvs)/len(cvs)
    else:
        results["cv_isi"] = 0

    # calculate global cross-correlation
    #cc_matrix = corrcoef(BinnedSpikeTrain(spiketrains, binsize=5*ms))
    #results["cc_min"] = cc_matrix.min()
    #results["cc_max"] = cc_matrix.max()
    #results["cc_mean"] = cc_matrix.mean()

    io.close()
    return results


if os.path.exists(statistics_file):
    # read the previously calculated spike train statistics from file
    data = pandas.read_csv(statistics_file,
                           delim_whitespace=True)
else:
    # for each data file, read the spike trains and calculate the metrics
    data = pandas.read_csv(os.path.join(results_dir, "sweeps.csv"),
                           names=("g", "eta", "output_file"),
                           delim_whitespace=True, comment="#")

    # for idx, row in data.iterrows():
    #     results = spike_statistics(idx, row)
    #     for key, value in results.items():
    #         data.ix[idx, key] = value

    results = Parallel(n_jobs=4)(delayed(
                  spike_statistics)(idx, row) for idx, row in data.iterrows())
    for idx, result in enumerate(results):
        for key, value in result.items():
            data.ix[idx, key] = value


    print(data)

    # save statistics to file
    data.to_csv(os.path.join(results_dir, "statistics.csv"),
                sep=" ", index=False)


# build data structures for plotting
gvec = np.sort(data["g"].unique())
etavec = np.sort(data["eta"].unique())
print(gvec, etavec)
z = {
    "firing_rate": np.zeros((etavec.size, gvec.size)),
    "spike_counts": np.zeros((etavec.size, gvec.size), dtype=int),
    "cv_isi": np.zeros((etavec.size, gvec.size)),
    "cc_mean": np.zeros((etavec.size, gvec.size))
}

for idx, row in data.iterrows():
    # convert g and eta to i and j
    j = np.argwhere(gvec == row["g"])[0]
    i = np.argwhere(etavec == row["eta"])[0]
    for name in ("firing_rate", "cv_isi", ):  #"cc_mean"):
        z[name][i, j] = row[name]

# plot figure
x, y = np.meshgrid(gvec, etavec)
plt.figure(1)
plt.subplot(2, 2, 1)
plt.pcolormesh(x, y, z["firing_rate"], cmap='RdBu', vmin=0, vmax=z["firing_rate"].max())
plt.title('Firing rate')
plt.ylabel("eta")
plt.xlabel("g")
# set the limits of the plot to the limits of the data
plt.axis([x.min(), x.max(), y.min(), y.max()])
plt.colorbar()

plt.subplot(2, 2, 2)
plt.pcolormesh(x, y, z["cv_isi"], cmap='RdBu', vmin=0, vmax=z["cv_isi"].max())
plt.title('CV (ISI)')
plt.axis([x.min(), x.max(), y.min(), y.max()])
plt.colorbar()

# plt.subplot(2, 2, 3)
# plt.pcolormesh(x, y, z["cc_mean"], cmap='RdBu', vmin=0, vmax=z["cc_mean"].max())
# plt.title('Mean correlation coefficient')
# plt.axis([x.min(), x.max(), y.min(), y.max()])
# plt.colorbar()

plt.savefig(os.path.join(results_dir, "brunel_network_phase_plots.png"))
