
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from pages.pedidos.models import TentativaEntrega, Pedido
from django.db import transaction

from pages.pedidos.consumers import GRUPO_RELATORIO


@require_POST
@csrf_protect
@login_required
@permission_required('pedidos.change_tentativaentrega', raise_exception=True)
def relatorio_conferencia_salvar_view(request):
    data = request.sisvar_front or {}
    try:
        mov_id = int(data.get('id'))
        carro = data.get('carro')
        obs_rota = str(data.get('obs_rota') or '').strip()
        volume_conf = data.get('volume_conf')
        periodo = str(data.get('periodo') or '').strip().upper()
    except Exception:
        return JsonResponse({'success': False, 'mensagem': 'Dados inválidos.'}, status=400)

    try:
        with transaction.atomic():
            mov = TentativaEntrega.objects.select_related('pedido').filter(id=mov_id).first()
            if not mov:
                return JsonResponse({'success': False, 'mensagem': 'Movimentação não encontrada.'}, status=404)
            if carro is not None:
                mov.carro = int(carro) if str(carro).strip() else None
            if periodo in ('MANHA', 'TARDE'):
                mov.periodo = periodo
            elif periodo == '':
                mov.periodo = None
            mov.save(update_fields=['carro', 'periodo'])
            pedido = mov.pedido
            if pedido:
                pedido.obs_rota = obs_rota
                pedido.volume_conf = int(volume_conf) if str(volume_conf).strip() else 0
                pedido.save(update_fields=['obs_rota', 'volume_conf'])
    except Exception as exc:
        return JsonResponse({'success': False, 'mensagem': str(exc)}, status=422)

    # Broadcast via WebSocket para todos os usuários conectados à tela
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            GRUPO_RELATORIO,
            {
                "type": "relatorio_update",
                "payload": {
                    "id": mov.id,
                    "carro": mov.carro,
                    "obs_rota": pedido.obs_rota if pedido else None,
                    "volume_conf": pedido.volume_conf if pedido else None,
                    "periodo": mov.periodo,
                },
            },
        )
    except Exception:
        # Falha no broadcast não deve impedir a resposta de sucesso
        pass

    return JsonResponse({'success': True})
