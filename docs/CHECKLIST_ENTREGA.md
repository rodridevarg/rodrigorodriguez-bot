# Checklist de Entrega - Nuevo Cliente

> Usar este checklist antes de entregar un bot a un cliente nuevo.

---

## Pre-entrega (antes de que el cliente use el bot)

### Documentos
- [ ] `data/docs/home.md` — presentacion del negocio completa
- [ ] `data/docs/servicios.md` — todos los servicios/productos listados
- [ ] `data/docs/precios.md` — precios actualizados (si aplica)
- [ ] `data/docs/faq.md` — al menos 10 preguntas frecuentes
- [ ] `data/docs/horarios.md` — dias y horarios de atencion
- [ ] `data/docs/contacto.md` — telefono, email, direccion, redes
- [ ] Documentos reindexados (`scripts/index_documents.py` ejecutado sin errores)

### Prompt y comportamiento
- [ ] `data/system_prompt.txt` editado con tono adecuado al rubro
- [ ] El bot NO inventa precios ni promesas que no esten en los documentos
- [ ] El bot redirige al telefono de contacto cuando no sabe algo
- [ ] Respuestas en espanol, claras y profesionales

### WhatsApp
- [ ] `WHATSAPP_MODE` configurado correctamente (`fake` para demo, `meta` para produccion)
- [ ] Si `meta`: token valido, numero verificado, webhook registrado en Meta Dashboard
- [ ] Numero de telefono de contacto correcto en `.env`

### Panel de administracion
- [ ] `ADMIN_API_KEY` generada y guardada en lugar seguro
- [ ] Panel admin accesible en `https://{dominio}/admin`
- [ ] Funciona "Tomar control", "Liberar" y "Responder manualmente"
- [ ] Notificaciones con sonido funcionan (requiere interaccion primero)

### Dominio y HTTPS
- [ ] Subdominio responde con HTTPS (certificado valido)
- [ ] `https://{dominio}/health` responde `{"status": "ok"}`
- [ ] `https://{dominio}/chat` carga el chat web
- [ ] No hay errores 404 ni 502

### Pruebas de conversacion
- [ ] Probar 5-10 conversaciones tipicas del rubro
- [ ] Verificar que el bot usa las fuentes correctas
- [ ] Verificar fallback cuando no hay informacion
- [ ] Verificar handoff a humano funciona

## Entrega al cliente

- [ ] Enviar URL del panel admin
- [ ] Enviar `ADMIN_API_KEY` por canal seguro
- [ ] Explicar como funciona "Tomar control" y "Responder"
- [ ] Explicar que el bot aprende de los documentos (no adivina)
- [ ] Dejar claro el canal de soporte (tu email/WhatsApp)
- [ ] Confirmar precio, plan y proxima fecha de facturacion

## Post-entrega (primeros 7 dias)

- [ ] Revisar conversaciones diariamente (panel admin)
- [ ] Corregir respuestas incorrectas editando documentos
- [ ] Reindexar despues de cada cambio importante
- [ ] Preguntar al cliente si esta satisfecho (dia 3 y dia 7)
- [ ] Ajustar prompt si el tono no encaja con la marca del cliente

---

*Ultima actualizacion: 2026-05-28*
