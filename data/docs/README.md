# Guía para el Operador

## Qué documentos subir

La base de conocimiento del bot se alimenta de archivos `.md` (Markdown) ubicados en esta carpeta (`data/docs/`).

Cada archivo representa una sección de conocimiento. El bot usa búsqueda semántica para encontrar la información relevante cuando un cliente pregunta.

## Archivos recomendados

| Archivo | Contenido |
|---------|-----------|
| `home.md` | Presentación general del negocio, qué hacen, propuesta de valor |
| `servicios.md` | Lista detallada de servicios/productos, descripciones, características |
| `precios.md` | Precios, planes, formas de pago. **NO inventar precios** si no están acá |
| `faq.md` | Preguntas frecuentes y respuestas claras |
| `horarios.md` | Días y horarios de atención, zona horaria |
| `contacto.md` | Dirección, email, teléfono, redes sociales, mapa |
| `proceso.md` | Cómo contratar, pasos a seguir, tiempos de entrega |
| `sobre-mi.md` | Historia del negocio, equipo, valores (opcional) |

## Reglas de formato

1. **Usá Markdown simple**: títulos (`#`), listas (`-`), negrita (`**texto**`).
2. **Sé conciso pero completo**: la IA lee los documentos como contexto. Cuanta más info relevante, mejor.
3. **Un tema por archivo**: no mezcles precios con horarios en el mismo archivo. Facilita la búsqueda semántica.
4. **Actualizá con frecuencia**: si cambian precios o servicios, editá el archivo y reindexá.

## Cómo reindexar

Después de modificar o agregar documentos, ejecutá:

```bash
python scripts/index_documents.py
```

Esto regenera los embeddings en ChromaDB para que el bot use la información actualizada.

## Prompt del sistema

El comportamiento de la IA se define en `data/system_prompt.txt`.
Editalo para ajustar el tono (formal, casual, técnico, etc.) y las instrucciones específicas del negocio.
