import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(layout='wide')
st.title('KORA | Conociendo clientes')
st.caption('Corte: 31/10/2026')

# 1. Cargar y preparar los datos (diapositivas 11 a 14)
clientes = pd.read_csv('KORA_clientes.csv', parse_dates=['fecha_registro'])
pedidos = pd.read_csv('KORA_pedidos.csv', parse_dates=['fecha_pedido'])
assert clientes.id_cliente.is_unique
assert pedidos.id_pedido.is_unique

resumen = pedidos.groupby('id_cliente').agg(
    n_pedidos=('id_pedido', 'nunique'),
    ingreso_total=('ingreso_neto_cop', 'sum'),
    ultima_compra=('fecha_pedido', 'max')
).reset_index()
perfil = clientes.merge(resumen, how='left', on='id_cliente', validate='one_to_one')
perfil['n_pedidos'] = perfil.n_pedidos.fillna(0)
perfil['ingreso_total'] = perfil.ingreso_total.fillna(0)
fecha_corte = pd.Timestamp('2026-10-31')
perfil['dias_sin_compra'] = (fecha_corte - perfil.ultima_compra).dt.days

def segmento(f):
    if f.n_pedidos == 0: return 'Sin compra'
    if f.dias_sin_compra > 90: return 'En pausa'
    if f.n_pedidos >= 3: return 'Fieles'
    if f.n_pedidos == 1: return 'Primerizos'
    return 'En desarrollo'

perfil['segmento'] = perfil.apply(segmento, axis=1)

# 2. Filtros: todos los cálculos usan el mismo subconjunto
ciudades = st.sidebar.multiselect('Ciudad', sorted(perfil.ciudad.unique()),
                                  default=sorted(perfil.ciudad.unique()))
canales = st.sidebar.multiselect('Canal de adquisición', sorted(perfil.canal_adquisicion.unique()),
                                 default=sorted(perfil.canal_adquisicion.unique()))
segmentos = st.sidebar.multiselect('Segmento', sorted(perfil.segmento.unique()),
                                   default=sorted(perfil.segmento.unique()))
preferencias = st.sidebar.multiselect('Preferencia declarada', sorted(perfil.preferencia_declarada.unique()),
                                      default=sorted(perfil.preferencia_declarada.unique()))

filtrado = perfil[
    perfil.ciudad.isin(ciudades) &
    perfil.canal_adquisicion.isin(canales) &
    perfil.segmento.isin(segmentos) &
    perfil.preferencia_declarada.isin(preferencias)
]
compradores = filtrado[filtrado.n_pedidos > 0].copy()
pedidos_f = pedidos[pedidos.id_cliente.isin(filtrado.id_cliente)].copy()

# 3. Indicadores originales y nuevos
n_compradores = len(compradores)
recompra = compradores.n_pedidos.ge(2).mean() if n_compradores else 0
ingreso = filtrado.ingreso_total.sum()
n_pedidos = filtrado.n_pedidos.sum()
una_compra = compradores.n_pedidos.eq(1).sum()
porcentaje_una = una_compra / n_compradores if n_compradores else 0

a, b, c, d = st.columns(4)
a.metric('Compradores', n_compradores)
b.metric('Recompra', f'{recompra:.1%}' if n_compradores else 'N/D')
c.metric('Ingreso COP', f'{ingreso/1e6:.1f} M')
d.metric('Ticket COP', f'{ingreso/n_pedidos:,.0f}' if n_pedidos else 'N/D')
e, f = st.columns(2)
e.metric('Compradores con 1 pedido', int(una_compra))
f.metric('% compradores con 1 pedido', f'{porcentaje_una:.1%}' if n_compradores else 'N/D')
st.subheader('Clientes por segmento')

tabla = filtrado.groupby('segmento').size().reset_index(name='clientes')
st.plotly_chart(px.bar(tabla, x='segmento', y='clientes', text='clientes'),
                use_container_width=True)

st.subheader('Ingreso neto por categoría')
cat = pedidos_f.groupby('categoria', as_index=False)['ingreso_neto_cop'].sum()
st.plotly_chart(px.bar(cat, x='ingreso_neto_cop', y='categoria', orientation='h'),
                use_container_width=True)

st.subheader('Evolución mensual de pedidos')
pedidos_f['mes'] = pedidos_f.fecha_pedido.dt.to_period('M').astype(str)
serie = pedidos_f.groupby('mes').size()
if len(serie):
    st.plotly_chart(px.line(x=serie.index, y=serie.values, markers=True),
                    use_container_width=True)
else:
    st.write('No hay pedidos para mostrar con estos filtros.')

# 5. Laboratorio: tasa de recompra y oportunidad por canal
st.subheader('¿En qué canal probar una campaña de segunda compra?')
st.write('La tasa de recompra mide compradores con 2 o más pedidos / compradores con al menos 1 pedido. '
         'No basta por sí solal,también importa cuántos compradores tienen exactamente 1 pedido, '
         'pues representan el público potencial de la campaña.')

compradores['repite'] = compradores.n_pedidos.ge(2)
compradores['tiene_un_pedido'] = compradores.n_pedidos.eq(1)
por_canal = compradores.groupby('canal_adquisicion').agg(
    compradores=('id_cliente', 'count'),
    repetidores=('repite', 'sum'),
    una_compra=('tiene_un_pedido', 'sum')
).reset_index()

if len(por_canal):
    por_canal['tasa_recompra'] = 100 * por_canal.repetidores / por_canal.compradores

    st.write('Tasa de recompra por canal. Las barras permiten comparar porcentajes; '
             'al pasar el cursor se muestra el número de compradores (denominador).')
    fig = px.bar(por_canal, x='canal_adquisicion', y='tasa_recompra',
                 custom_data=['compradores'], labels={'tasa_recompra': 'Recompra (%)',
                 'canal_adquisicion': 'Canal'})
    fig.update_traces(hovertemplate='Canal: %{x}<br>Recompra: %{y:.1f}%<br>'
                                    'Compradores: %{customdata[0]}<extra></extra>')
    st.plotly_chart(fig, use_container_width=True)

    st.write('**Compradores con exactamente un pedido por canal.** '
             'Las barras se ordenan de mayor a menor oportunidad en volumen.')
    ordenado = por_canal.sort_values('una_compra', ascending=False)
    fig = px.bar(ordenado, x='canal_adquisicion', y='una_compra', text='una_compra',
                 labels={'una_compra': 'Compradores con 1 pedido',
                         'canal_adquisicion': 'Canal'})
    st.plotly_chart(fig, use_container_width=True)

    st.write('El canal con más compradores de una sola compra no tiene necesariamente '
             'la menor tasa de recompra: son métricas distintas y deben contrastarse.')

    elegido = ordenado.iloc[0]
    st.subheader('Recomendación para el piloto')
    st.write(f"Recomiendo probar primero en **{elegido.canal_adquisicion}**: "
             f"tiene **{int(elegido.una_compra)} compradores con una sola compra** y "
             f"una **tasa de recompra del {elegido.tasa_recompra:.1f}%**. "
             'Es una oportunidad por volumen, no una prueba de efectividad. '
             'Limitación: no sabemos por qué los clientes no han vuelto a comprar. '
             'Evaluaría un piloto aleatorizado comparando la tasa de segunda compra '
             'del grupo contactado contra un grupo de control.')
else:
    st.warning('No hay compradores con los filtros seleccionados. No se calculan tasas sin denominador.')

st.caption('Prueba los filtros por ciudad, canal, segmento y preferencia; '
           'si no quedan compradores, las tasas aparecen como N/D.')
