import matplotlib.pyplot as plt

from config import OUTPUTS_DIR


def plot_correlation_matrix(corr_matrix, save_path=None):
    """Save the correlation matrix as a heatmap PNG."""
    if save_path is None:
        save_path = OUTPUTS_DIR / 'correlation_matrix.png'

    fig, ax = plt.subplots(figsize=(14, 12))
    n = len(corr_matrix)
    im = ax.imshow(corr_matrix.values, cmap='RdYlGn', vmin=-1, vmax=1, aspect='auto')
    plt.colorbar(im, ax=ax, label='Correlación de Pearson')

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(corr_matrix.columns, rotation=45, ha='right', fontsize=9)
    ax.set_yticklabels(corr_matrix.columns, fontsize=9)

    for i in range(n):
        for j in range(n):
            val = corr_matrix.values[i, j]
            color = 'black' if 0.3 < abs(val) < 0.8 else 'white'
            ax.text(j, i, f'{val:.2f}', ha='center', va='center', fontsize=7, color=color)

    ax.set_title('Matriz de Correlación — Top 20 S&P 500 (90 días)', fontsize=14, pad=16)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Matriz guardada en: {save_path}")
