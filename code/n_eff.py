'''
Copyright (c) 2025 Frederik Rytter and Kvantify Aps

Permission is hereby granted, free of charge, to any person obtaining 
a copy of this software and associated documentation files (the "Software"), 
to deal in the Software without restriction, including without limitation 
the rights to use, copy, modify, merge, publish, distribute, sublicense, 
and/or sell copies of the Software, and to permit persons to whom the 
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included 
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL 
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, 
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN 
THE SOFTWARE.
'''


import numpy as np
import matplotlib.pyplot as plt
from qiskit import QuantumCircuit
from qiskit.circuit.library import QFT


'''
Returns quantum circuits used to measure n_eff.
The inputs are ''n_epsilon'' and ''ns'', where the latter is the range
of qubits in which we expect to find n_eff, starting at n => 2.
The output is a dict with keys ''ns'' and value for each ''n'' in ''ns'',
''[circuit1(n), circuit2(n), ...]'', a list of circuits to run on hardware.
'''
def get_circuits(ns, n_epsilon):
    if min(ns) < 2:
        raise Exception(f"The smallest qubit count on which measurements needs to be done is n = 2. The smallest value given in ''ns'' is {min(ns)} < 2.")
    else:
        circuits = {n: [] for n in ns}
        Phi = [1/12, 1/6, 1/3, 5/12, 7/12, 2/3, 5/6, 11/12]
        for n in ns:
            for phi in Phi:
                # Intialize quantum circuit.
                qc = QuantumCircuit(n+1, n)

                # Implement QPE circuit.
                qc.h(range(n))
                qc.x(-1)
                for i in range(n):
                    qc.cp(2*np.pi*phi*2**(n-1-i), control_qubit=i, target_qubit=-1)
                qc.compose(QFT(n, inverse=True, do_swaps=False).decompose(), qubits=range(n), inplace=True)

                # Add measurements.
                qc.measure(range(n), range(n))

                # Save circuit.
                circuits[n] += [qc]*n_epsilon
        return circuits


'''
Returns the effective qubit number n_eff.
The first input are the ''data'' obtained from running ''circuits'' given by ''get_circuits''
on hardware. This should be a dict with same keys (''ns'') as ''circuits'' and value for each ''n'' in ''ns'',
''[data1, data2, ...]'', being a list of measurement outcomes datai obtained by running circuiti on
''n'' qubits on hardware with n_s = 100 shots. The measurement outcomes datai should also be a dict, but
with keys being bitstring outcomes ''m'' with ''n(m)'' != 0 and values ''n(m)''. The rightmost bit should
be the least significant one, i.e., correspond to the topmost qubit in the quantum circuits.
The second input ''display'' defaults to False, but if True, then the data used to compute ''n_eff''
is visualized. 
'''
def compute_n_eff(data, display=False):
    # Fixed quantities.
    Phi = [1/12, 1/6, 1/3, 5/12, 7/12, 2/3, 5/6, 11/12]
    ns = list(data.keys())
    n_epsilon = int(len(data[ns[0]])/len(Phi))

    # Compute mean experimental numerical accuracy.
    epsilon_est = {n: [0 for _ in range(n_epsilon)] for n in ns}
    for n in ns:
        for i in range(n_epsilon):
            for j, phi in enumerate(Phi):
                # Compute argmax of empirical probability distribution.
                counts = data[n][i + j*n_epsilon]
                argmax_bitstring = max(counts, key=counts.get)
                argmax = int(argmax_bitstring, 2)

                # Compute phase estimate.
                phi_est = argmax/(2**n)

                # Compute numerical error.
                error = abs(phi - phi_est)

                # Due to periodicity of exp(2*pi*i*x), x=0 and x=1 are "identical", so if 0 or 1 is the outcome of QPE, choose whichever one produces the smallest error.
                if phi_est == 0:
                    if error > abs(phi - 1):
                        error = abs(phi - 1)
                elif phi_est == 1:
                    if error > abs(phi - 0):
                        error = abs(phi - 0)

                # Save numerical error.
                epsilon_est[n][i] += 3*error/(4*len(Phi))
    mu_epsilon = [np.mean(errors) for errors in epsilon_est.values()]

    # Compute standard error.
    alpha_epsilon = [np.std(errors, ddof=1)/np.sqrt(n_epsilon-1) for errors in epsilon_est.values()]

    # Compute mean experimental loss and theoretical gain of numerical accuracy.
    delta_gain = [1/(2**(n+2)) for n in ns]
    Delta_loss = [error - 1/(2**(n+2)) for n, error in zip(ns, mu_epsilon)]

    # Compute success criterions.
    S = []
    for i, n in enumerate(ns):
        if Delta_loss[i] + alpha_epsilon[i] < delta_gain[i]:
            S.append(1)
        else:
            S.append(0)
            break

    # Compute n_eff.
    n_eff = 1 + sum(S)

    # Plot results.
    if display:
        fig, ax = plt.subplots(figsize=(6, 4))

        # Compute and plot epsilon.
        epsilon = [1/(2**(n+2)) for n in ns]
        ax.plot(ns, epsilon, marker="o", ms=7, color="skyblue", ls="--", label=r"$\epsilon(n)$")

        # Plot mu_epsilon and its standard error.
        ax.plot(ns, mu_epsilon, color="tomato", marker="o", ms=7, label=r"$\mu_{\epsilon}(n)$")
        lower_bound = [-alpha + error for alpha, error in zip(alpha_epsilon, mu_epsilon)]
        upper_bound = [alpha + error for alpha, error in zip(alpha_epsilon, mu_epsilon)]
        ax.fill_between(ns, lower_bound, upper_bound, color="tomato", alpha=0.3, label=r"$\alpha_{\epsilon}(n)$")

        # Plot n_eff.
        if n_eff >= 2:
            min_error = mu_epsilon[ns.index(n_eff)]
            ax.scatter(n_eff, min_error, c="white", edgecolor="black", zorder=3, s=50, label=r"$n_{eff} = $"+f"{n_eff}")
        else:
            ax.scatter(ns[0], mu_epsilon[0], c="white", edgecolor="black", zorder=3, alpha=0, s=50, label=r"$n_{eff} = $"+f"{n_eff}")

        ax.set_xlabel("n")
        ax.set_xticks(ns)
        ax.set_ylabel("Error")
        ax.set_yscale("log")
        ax.legend()
        ax.grid()
        plt.show()

    return n_eff