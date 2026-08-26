// Registro de suscripciones de alertas del Climómetro (Vercel Function).
//
// El portal manda {telefono, tipos[], sitios[], nombre}. Validamos, normalizamos
// a formato internacional (+52 por defecto) y reenviamos al webhook central si
// está configurado (SUSCRIPCIONES_WEBHOOK — el punto de integración con
// Hamilton/Sonar, donde vivirá el motor de alertamiento). Sin webhook, el
// registro queda aceptado y logueado: el portal guarda la configuración local
// y la central lo sincroniza cuando se conecte.
export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ ok: false, error: 'Solo POST' });
  }
  const { telefono, tipos, sitios, nombre } = req.body || {};
  const tel = String(telefono || '').replace(/[^\d+]/g, '');
  if (!/^\+?\d{10,15}$/.test(tel)) {
    return res.status(400).json({ ok: false, error: 'Número inválido: usa 10 dígitos (MX) o formato internacional con +.' });
  }
  if (!Array.isArray(tipos) || tipos.length === 0) {
    return res.status(400).json({ ok: false, error: 'Selecciona al menos un tipo de alerta.' });
  }
  const registro = {
    telefono: tel.startsWith('+') ? tel : '+52' + tel,
    tipos: tipos.slice(0, 10).map(String),
    sitios: Array.isArray(sitios) ? sitios.slice(0, 30) : [],
    nombre: String(nombre || '').slice(0, 80),
    ts: new Date().toISOString(),
  };
  let entregado = false;
  const hook = process.env.SUSCRIPCIONES_WEBHOOK;
  if (hook) {
    try {
      const r = await fetch(hook, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(registro),
      });
      entregado = r.ok;
    } catch (e) { /* la central sincroniza después */ }
  }
  console.log('suscripcion', JSON.stringify(registro), 'entregado:', entregado);
  return res.status(200).json({ ok: true, entregado, telefono: registro.telefono });
}
