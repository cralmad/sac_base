import { AppLoader } from '/static/js/loader.js';
import {
  getDataset,
  getCsrfToken,
  clearMessages,
  definirMensagem,
  updateState,
} from '/static/js/sisVar.js';

const LABELS_STATS = {
  total_lidas: 'Total de linhas lidas',
  ignoradas: 'Duplicatas ignoradas',
  criados: 'Pedidos criados',
  atualizados: 'Pedidos atualizados',
  sem_alteracao: 'Pedidos sem alteração',
  tentativas: 'Tentativas criadas',
  avisos_fk: 'Avisos de FK não resolvida',
  coords_atribuidas: 'Coordenadas atribuídas',
  coords_cp_pt: 'Geocode CP (cp_pt)',
  coords_cp_pt_rua: 'Geocode morada (cp_pt_rua)',
  coords_cp_pt_fallback: 'Geocode fallback (1ª opção)',
  coords_enfileiradas: 'Enfileirados (noturno)',
  coords_restantes_filial: 'Restantes sem coordenadas',
  coords_cp_nao_encontrado: 'CP sem GPS no site',
  geocode_modo: 'Modo geocodificação',
};

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

function exibirStats(stats) {
  const div = document.getElementById('resultado-importacao');
  const tbody = document.getElementById('tabela-stats');
  tbody.innerHTML = '';
  Object.entries(LABELS_STATS).forEach(([key, label]) => {
    if (key in stats) {
      const tr = document.createElement('tr');
      const tdLabel = document.createElement('td');
      tdLabel.textContent = String(label ?? '');

      const tdValor = document.createElement('td');
      tdValor.className = 'text-end';
      let valor = stats[key];
      if (key === 'geocode_modo') {
        valor = valor === 'noturno' ? 'Noturno (Scheduler)' : 'Síncrono';
      }
      tdValor.textContent = String(valor ?? '');

      tr.appendChild(tdLabel);
      tr.appendChild(tdValor);
      tbody.appendChild(tr);
    }
  });
  div.classList.remove('d-none');
}

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

function processarMensagensGeocode(data) {
  if (data.mensagens && Object.keys(data.mensagens).length) {
    updateState({ mensagens: data.mensagens });
    return;
  }
  const stats = data.stats || {};
  if (stats.geocode_site_ok === false) {
    definirMensagem(
      'erro',
      'codigo-postal.pt indisponível ou com estrutura alterada.',
      false,
    );
  }
}

document.addEventListener('DOMContentLoaded', () => {
  preencherFiliais();

  const form = document.getElementById('formImportacao');
  const btnBaixar = document.getElementById('btn-baixar-relatorio');
  const btnGeocodificar = document.getElementById('btn-geocodificar');
  let ultimoRelatorio = null;
  let ultimoNomeRelatorio = 'relatorio_importacao.txt';

  btnBaixar.addEventListener('click', () => {
    if (ultimoRelatorio) {
      baixarRelatorio(ultimoRelatorio, ultimoNomeRelatorio);
    }
  });

  btnGeocodificar?.addEventListener('click', async () => {
    clearMessages();
    const filialId = document.getElementById('filial_id')?.value;
    if (!filialId) {
      definirMensagem('erro', 'Selecione uma filial.');
      return;
    }

    const formData = new FormData();
    formData.append('filial_id', filialId);

    AppLoader.show();
    try {
      const resp = await fetch('/app/logistica/pedidos/geocodificar-sem-coordenadas/', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken() },
        body: formData,
      });
      const data = await resp.json();
      processarMensagensGeocode(data);
      if (data.success) {
        exibirStats(data.stats || {});
      }
    } catch {
      definirMensagem('erro', 'Erro de comunicação com o servidor.');
    } finally {
      AppLoader.hide();
    }
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearMessages();

    const filialId = document.getElementById('filial_id').value;
    const arquivoInput = document.getElementById('arquivo_csv');
    const verificarVolumes = document.getElementById('verificar_volumes')?.checked ? '1' : '0';
    const analisarMovimentacoesDia = document.getElementById('analisar_movimentacoes_dia')?.checked ? '1' : '0';

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
    formData.append('verificar_volumes', verificarVolumes);
    formData.append('analisar_movimentacoes_dia', analisarMovimentacoesDia);

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
        baixarRelatorio(ultimoRelatorio, ultimoNomeRelatorio);
        if (data.relatorio_volumes_url) {
          window.open(data.relatorio_volumes_url, '_blank');
        }
        form.reset();
      }
    } catch {
      definirMensagem('erro', 'Erro de comunicação com o servidor.');
    } finally {
      AppLoader.hide();
    }
  });
});
