import { AppLoader } from '/static/js/loader.js';
import {
  getDataset,
  getCsrfToken,
  clearMessages,
  definirMensagem,
  updateState,
} from '/static/js/sisVar.js';

const LABELS_STATS = {
  total_lidas:    'Total de linhas lidas',
  ignoradas:      'Duplicatas ignoradas',
  criados:        'Pedidos criados',
  atualizados:    'Pedidos atualizados',
  sem_alteracao:  'Pedidos sem alteração',
  tentativas:     'Tentativas criadas',
  avisos_fk:      'Avisos de FK não resolvida',
};

// Preenche o select de filiais a partir da sisVar
function preencherFiliais() {
  const select = document.getElementById('filial_id');
  const filiais = getDataset('filiais_escrita') || [];
  filiais.forEach(f => {
    const opt = document.createElement('option');
    opt.value = f.id;
    opt.textContent = `${f.codigo} - ${f.nome}`;
    select.appendChild(opt);
  });
}

// Exibe a tabela de estatísticas após importação
function exibirStats(stats) {
  const div = document.getElementById('resultado-importacao');
  const tbody = document.getElementById('tabela-stats');
  tbody.innerHTML = '';
  Object.entries(LABELS_STATS).forEach(([key, label]) => {
    if (key in stats) {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${label}</td><td class="text-end">${stats[key]}</td>`;
      tbody.appendChild(tr);
    }
  });
  div.classList.remove('d-none');
}

// Dispara o download do relatório como arquivo de texto
function baixarRelatorio(conteudo, nomeArquivo) {
  const blob = new Blob([conteudo], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = nomeArquivo;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

document.addEventListener('DOMContentLoaded', () => {
  preencherFiliais();

  const form = document.getElementById('formImportacao');
  const btnBaixar = document.getElementById('btn-baixar-relatorio');
  let ultimoRelatorio = null;
  let ultimoNomeRelatorio = 'relatorio_importacao.txt';

  btnBaixar.addEventListener('click', () => {
    if (ultimoRelatorio) {
      baixarRelatorio(ultimoRelatorio, ultimoNomeRelatorio);
    }
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearMessages();

    const filialId = document.getElementById('filial_id').value;
    const arquivoInput = document.getElementById('arquivo_csv');

    if (!filialId) {
      definirMensagem('erro', 'Selecione uma filial.');
      return;
    }
    if (!arquivoInput.files.length) {
      definirMensagem('erro', 'Selecione um arquivo CSV.');
      return;
    }

    const formData = new FormData();
    formData.append('filial_id', filialId);
    formData.append('arquivo_csv', arquivoInput.files[0]);

    AppLoader.show();
    btnBaixar.classList.add('d-none');
    document.getElementById('resultado-importacao').classList.add('d-none');

    try {
      const resp = await fetch('/app/logistica/pedidos/importar', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken() },
        body: formData,
      });

      const data = await resp.json();

      if (data.mensagens) {
        updateState({ mensagens: data.mensagens });
      }

      if (data.success) {
        ultimoRelatorio = data.relatorio;
        ultimoNomeRelatorio = data.nome_relatorio || 'relatorio_importacao.txt';
        exibirStats(data.stats || {});
        btnBaixar.classList.remove('d-none');
        // Dispara o download automaticamente após importação
        baixarRelatorio(ultimoRelatorio, ultimoNomeRelatorio);
        form.reset();
      }
    } catch (err) {
      definirMensagem('erro', 'Erro de comunicação com o servidor.');
    } finally {
      AppLoader.hide();
    }
  });
});
