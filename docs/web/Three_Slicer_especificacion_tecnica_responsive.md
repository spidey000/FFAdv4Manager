# Three Slicer: especificación técnica de interfaz responsive

Versión 1.0 · 20 de octubre de 2026 · Diseño aprobado para móvil y tablet

## 1. Resultado que debe producir la implementación

Adaptar la interfaz de Three Slicer para preparar modelos, configurar el proceso, laminar y examinar el resultado mediante pantalla táctil. El visor 3D será el área principal. En móvil, los ajustes ocuparán un panel inferior regulable; en tablet ancha, un inspector lateral plegable. Ambos compartirán proyecto, selección, cámara y configuración.

Las dos maquetas aprobadas definen el lenguaje visual: visor oscuro, superficies claras para ajustes y verde para acciones y selección. Sus dimensiones y textos se concretan aquí. Si una maqueta y esta especificación discrepan en accesibilidad, comportamiento o límites del motor, prevalece esta especificación.

El ejemplo Adventurer 4 representa un perfil personalizado. La adaptación visual no acredita por sí misma compatibilidad de su G-code ni añade conectividad con la impresora.

### Alcance

- Importación y gestión de modelos/proyectos con los formatos y comportamientos existentes.
- Transformaciones, selección, placas, materiales, pintura y configuración accesibles mediante tacto.
- Configuración rápida y acceso a todas las opciones avanzadas disponibles.
- Preparación, laminado, cancelación, previsualización, estadísticas y exportación.
- Conservación de ámbitos global/placa, tecnología FFF/SLA y restricciones existentes.
- Adaptación al contenedor, orientación, teclado virtual, ratón, teclado físico y lápiz.

No forma parte de esta tarea implementar algoritmos de laminado, nuevas funciones por pieza/rango de altura, protocolos de impresora, una aplicación nativa ni persistencia automática del proyecto entre recargas. Estas capacidades requieren su propio alcance si no están disponibles en la versión integrada.

## 2. Base de código comprobada y límites actuales

Repositorio canónico: https://github.com/kimgh06/Three_Slicer

Espejo del visor: https://github.com/kimgh06/three-slicer-viewer

La revisión técnica se ha realizado sobre el árbol del espejo con SHA `b3ab1b9183278d103b7ddbdcee3198036174bf2e`. Antes de desarrollar, fijar la versión del monorepositorio y comprobar su correspondencia con este árbol. Las rutas `src/...`, `styles.css` y `types/...` citadas abajo son relativas al paquete del visor; en el monorepositorio se sitúan bajo `viewer-package/`.

Hallazgos relevantes:

| Pieza actual | Situación comprobada | Consecuencia para el desarrollo |
| --- | --- | --- |
| `src/Viewport.jsx` | Compone la escena, barras, tarjetas y acciones; mantiene numerosos estados y referencias internas. | Reorganizar su presentación sin duplicar el propietario de la escena. |
| `styles.css` | Estructura de escritorio, panel derecho de 384 px, controles pequeños y sin reglas `@media` en el archivo revisado. | Introducir distribución adaptable y tamaños táctiles. |
| Shadow DOM | El visor y el formulario de ajustes tienen estilos encapsulados. | Cambiar ambos juegos de estilos; el CSS de la página contenedora no basta. |
| `src/scene/use_three_scene.js` | Posee renderer, cámara, controles, selección y una API interna. Ya observa el tamaño del montaje. | Mantener su instancia y revisar el arbitraje entre selección, cámara, transformación y pintura. |
| `src/ui/ProcessCard.jsx` | Proyecta ajustes efectivos y setter según ámbito global/placa. | Reutilizar esa proyección en los controles rápidos y avanzados. |
| `src/components/SettingsPanel.jsx` | Formulario por esquema; conserva búsqueda y filtros en estado local; incluye un segundo Shadow DOM. | Añadir control de presentación y adaptar widgets sin perder reglas ni tipos. |
| `types/viewer.d.ts` | Expone configuración, slots de paneles, eventos y solicitud de laminado. | Respetar la API pública e introducir nuevas props únicamente si son necesarias. |

### Qué permite hoy la API pública

`settings`/`setSettings`, `plateSettings`/`setPlateSettings`, `processPanel`, `filamentPanel`, `motionPanel`, `panels`, `features`, `sliceRequest`, `onEvent`, `onSliced`, `onSliceRun` y `onExport` permiten componer una integración parcial. Los eventos informan, entre otras cosas, del modo, objetos, placa, laminado y capas.

Eso no equivale a un controlador externo completo: no hay un contrato público general para seleccionar, transformar o pintar objetos desde una interfaz independiente. `files` se procesa inicialmente al montar y no es una orden genérica de importación en tiempo de ejecución. No diseñar botones externos que dependan de métodos públicos inexistentes.

**Estrategia elegida:** modificar la composición interna del visor y sus componentes. Evitar automatizar botones del Shadow DOM, simular clics o mantener una segunda escena como solución de integración.

## 3. Reglas de distribución

### 3.1 Adaptación por tamaño del contenedor

Medir el contenedor del slicer mediante `ResizeObserver`, no identificar modelos de dispositivo ni depender únicamente del ancho de `window`.

| Variante | Ancho disponible | Distribución |
| --- | --- | --- |
| Compacta | <768 px CSS | Cabecera, selector de modo, visor, panel inferior, acción principal y navegación inferior. |
| Intermedia | 768–959 px CSS | Visor dominante, herramientas accesibles y ajustes en panel superpuesto bajo demanda. |
| Expandida | ≥960 px CSS | Cabecera; columna de herramientas; visor; inspector derecho; acción al pie del inspector. |

Estos umbrales son valores iniciales del producto. En la variante expandida debe quedar al menos 480 px de ancho para la escena: si el inspector elegido o un contenedor especial impiden cumplirlo, usar la variante intermedia. La preferencia manual de plegado del inspector se conserva.

La precisión del puntero es independiente del ancho. Una tablet grande sigue necesitando controles táctiles; un portátil estrecho conserva sus atajos. Utilizar `pointer`/`any-pointer` como señales complementarias y `PointerEvent.pointerType` para cada interacción.

### 3.2 Dimensiones de referencia

| Elemento | Dimensión propuesta |
| --- | --- |
| Cabecera | 56 px, más área segura superior cuando corresponda. |
| Selector de modo en móvil | Fila propia de 48 px. |
| Zona pulsable | Mínimo 48 × 48 px CSS. |
| Iconos | 20–24 px dentro de la zona pulsable. |
| Columna de herramientas | 64 px; más anchura si las etiquetas traducidas lo necesitan. |
| Inspector expandido | 320 px por defecto; rango inicial 300–340 px. |
| Acción principal | Botón de al menos 52 px; contenedor de altura mínima 76 px. |
| Navegación móvil | 64 px, más área segura inferior. |
| Padding de paneles | 16 px; 12 px en superficies especialmente compactas. |
| Separación de controles | 8–12 px. |
| Radios | 10–16 px. |
| Texto de entrada | 16 px mínimo. |

Evitar alturas rígidas en textos, etiquetas y tarjetas que deban crecer con traducciones o aumento de fuente.

### 3.3 Panel inferior móvil

Tres posiciones sobre el espacio de trabajo restante después de cabecera, selector de modo y pies:

- `collapsed`: tirador y resumen, aproximadamente 64 px.
- `half`: aproximadamente el 52 % del espacio de trabajo, ajustado para dejar al menos 180 px de visor cuando haya altura suficiente.
- `expanded`: ocupa el espacio de trabajo disponible; el visor puede quedar oculto temporalmente. Es una vista de edición explícita, con botón para volver al modelo.

No forzar el mínimo de visor cuando el teclado o una pantalla horizontal muy baja hacen imposible cumplirlo. En esos casos, priorizar el campo activo y presentar el inspector a altura completa. La vuelta al visor debe ser inmediata y visible.

El tirador permite arrastrar y también pulsar para cambiar de posición. Añadir botones equivalentes para expandir/recoger: el gesto no puede ser la única vía.

Capturar el puntero únicamente sobre el tirador; el contenido interno conserva su scroll vertical. El desplazamiento del formulario nunca debe arrastrar el panel ni mover la cámara. Al soltar, ajustar al punto más cercano; usar velocidad como criterio secundario, con umbral inicial de 0,6 px/ms que deberá validarse en dispositivos reales. Animación de asentamiento: 160–220 ms, desactivable con `prefers-reduced-motion`.

En posiciones recogida e intermedia, el inspector forma parte de la distribución y reduce el área real del canvas. Así el render y el raycast comparten los mismos límites visibles. No cubrir medio canvas con un panel manteniendo su tamaño completo sin corregir el encuadre.

### 3.4 Tablet y modo horizontal corto

En ancho ≥960 px, el inspector es una columna normal. Plegarlo devuelve su espacio al visor. La acción principal se mantiene en un pie compacto accesible incluso con el inspector cerrado.

En 768–959 px, mostrar un panel lateral superpuesto de hasta `min(360px, ancho - 64px)`. Mientras el formulario superpuesto esté abierto, tratarlo como diálogo modal y bloquear los gestos de la escena que queda detrás. Ofrecer cierre visible.

En altura disponible <520 px y ancho compacto, recoger por defecto el panel y ofrecer edición a pantalla completa. No intentar mantener seis franjas de altura fija y un canvas inutilizable. Conservar la preferencia previa para restaurarla al volver a una orientación con espacio.

## 4. Arquitectura de componentes

Los nombres de esta sección son **componentes y contratos propuestos**, salvo los identificados expresamente como existentes. No se presentan como exports ya disponibles.

```text
Viewport                         // propietario actual, se conserva
  controlador y referencias de escena
  ResponsiveShell                // distribución, sin lógica del motor
    AppHeader                    // evolución de TopBar
      CanvasModeSwitch
    SceneSurface                 // montaje estable del canvas
    ToolDock                     // presentación de GizmoRail/ObjectToolbar
    ContextToolbar               // herramientas de la selección activa
    InspectorSurface             // una instancia de contenido editable
      InspectorSummary
      PrinterCard                // existente, adaptado
      FilamentCard / ResinCard   // existentes, según tecnología
      ObjectList                 // existente, adaptado
      ProcessCard                // existente, conserva ámbitos
        QuickSettings
        AdvancedSettings         // adaptación de SettingsPanel
      PreviewInspector           // PreviewControls + StatsCard
    PrimaryActionBar             // evolución de SliceBar
    MobileNavigation
    OverlayRoot                  // menús, ayuda, diálogos en el Shadow DOM
```

Este árbol es ilustrativo. La implementación debe conservar la identidad React y el mismo padre estable de `SceneSurface` entre variantes. No alternar entre `<MobileLayout><Viewport/></MobileLayout>` y `<TabletLayout><Viewport/></TabletLayout>`; eso desmontaría el visor.

### Responsabilidades

- **Controlador del visor:** acciones existentes, escena, historial, resultados y sincronización con el motor.
- **ResponsiveShell:** decide posiciones y superficies; no cambia parámetros de impresión.
- **InspectorSurface:** regula tamaño, scroll, foco y modalidad; no posee una copia de `settings`.
- **QuickSettings:** presenta una selección de opciones del esquema y escribe por el mismo setter que el formulario avanzado.
- **ToolDock/ContextToolbar:** muestran acciones del controlador y sus condiciones de disponibilidad.
- **PrimaryActionBar:** representa exactamente el estado de laminado/exportación existente, con presentación adaptable.
- **OverlayRoot:** aloja diálogos y menús dentro del encapsulamiento de estilos; evita portales indiscriminados a `document.body`.

Mantener una única instancia editable del formulario siempre que sea posible. Renderizar un formulario móvil y otro de tablet y esconder uno con CSS duplica IDs, suscripciones y estados locales; además puede perder la búsqueda al cambiar de variante.

## 5. Modelo de estado y contratos internos

Separar tres dominios:

1. **Proyecto y proceso:** configuración global, overrides por placa, geometría, materiales y pintura. Mantener propietarios y semántica actuales.
2. **Escena:** cámara, selección, herramienta, placas y referencias Three.js. Mantener en el controlador del visor.
3. **Presentación:** panel abierto, posición del panel, pestaña del inspector, búsqueda, categorías y diálogos. Nunca escribir estos valores en `settings`.

Contrato orientativo para el tercer dominio:

```ts
// NUEVO: contrato interno propuesto; no es la API actual del paquete.
type LayoutVariant = 'compact' | 'intermediate' | 'expanded';
type InspectorTab = 'model' | 'settings' | 'layers';
type SheetSnap = 'collapsed' | 'half' | 'expanded';
type EditingLevel = 'quick' | 'advanced';

interface ResponsiveUIState {
  inspectorTab: InspectorTab;
  sheetSnap: SheetSnap;
  inspectorOpen: boolean;
  editingLevel: EditingLevel;
  searchQuery: string;
  activeCategory: string | null;
  multiSelect: boolean;
  activeOverlay: null | 'more' | 'printer' | 'material' | 'help';
}
```

`LayoutVariant` y altura disponible son estado derivado de medición. No guardarlos como preferencia permanente. Conservar por separado posición preferida del panel y posición efectiva cuando teclado/altura obligan a una adaptación temporal.

Usar un reducer para transiciones relacionadas, o un hook de estado existente si mantiene las mismas invariantes. No incorporar una dependencia global únicamente para esta reorganización.

### Acciones internas de presentación

Definir un adaptador tipado sobre las funciones actuales, por ejemplo:

```ts
// NUEVO: ejemplo del contrato dentro del paquete, no métodos públicos actuales.
interface ResponsiveActions {
  setCanvasMode(mode: 'prepare' | 'preview'): void;
  requestSlice(scope: 'current' | 'all'): void;
  cancelSlice(): void;
  setTransformTool(tool: 'move' | 'rotate' | 'scale'): void;
  selectObjects(ids: number[]): void;
  frameSelection(): void;
  openProject(): void;
  addModels(): void;
}
```

Vincular cada operación a las funciones reales del `Viewport`. Si falta alguna, implementarla expresamente dentro del paquete y documentar su efecto. No añadir una fachada que simule funcionar con callbacks vacíos.

Las props nuevas que eventualmente se expongan deben ser aditivas, estar tipadas en `types/viewer.d.ts` y no cambiar el significado de `panels` ni `features`. Una prop pública de apariencia sería opcional; no es requisito para reorganizar internamente el visor.

## 6. Navegación y modos

### Cabecera

En móvil: marca, botón de apertura/adición con etiqueta accesible y menú de acciones secundarias. En tablet ancha: nombre de proyecto, apertura/adición, guardar, deshacer y rehacer según espacio. Mantener siempre accesibles las acciones existentes aunque algunas pasen al menú.

Distinguir claramente:

- **Abrir proyecto:** sustituye el contexto de trabajo con la semántica de apertura existente.
- **Añadir modelos:** incorpora geometría al proyecto actual si la acción implementada lo permite.

El código revisado identifica la apertura superior como una operación que limpia objetos existentes. No renombrarla simplemente a «+ Importar» prometiendo adición. Si se separan ambas rutas, deben tener callbacks y pruebas diferentes. Ante sustitución de trabajo sin guardar, proporcionar un flujo coherente de guardar/continuar/cancelar.

### Preparar / Vista previa

Un único valor canónico `canvasMode`. El selector superior y la navegación inferior delegan en la misma transición.

- `Preparar`: selección, transformación, configuración y pintura.
- `Vista previa`: trayectorias/capas y estadísticas del resultado disponible.
- Antes de tener capas, Vista previa y Capas aparecen deshabilitados, con explicación «Laminar para ver las capas» accesible sin hover.
- Un G-code importado puede permitir vista previa aunque no haya una escena editable. Respetar sus condiciones actuales de preparación y laminado.

### Navegación móvil

| Destino | Acción |
| --- | --- |
| Modelo | Activar Preparar cuando sea válido, recoger ajustes y mostrar selección/objetos/herramientas. |
| Ajustes | Abrir el inspector de configuración en la posición previa útil. No modificar parámetros por sí mismo. |
| Capas | Activar Vista previa y abrir controles de capas del resultado de la placa actual. |

Capas es un acceso contextual a Vista previa, no otro estado de motor. El estado activo de ambos controles debe ser coherente. Cambiar de destino nunca solicita un laminado implícito salvo que ya esté activado el comportamiento de laminado automático.

## 7. Ajustes rápidos y avanzados

### 7.1 Opciones rápidas FFF

Mostrar una cuadrícula de dos columnas cuando cada celda pueda conservar legibilidad; pasar a una columna en anchos muy pequeños o con texto ampliado.

| Etiqueta | Clave del esquema que debe verificarse al integrar | Presentación |
| --- | --- | --- |
| Altura de capa | `layer_height` | Número en mm. |
| Relleno | `sparse_infill_density` | Porcentaje, conservando su representación interna. |
| Paredes | `wall_loops` | Entero. |
| Soportes | `enable_support` | Sí/No; enlace a configuración detallada. |

Estas claves son el mapeo previsto de la familia OrcaSlicer. Resolverlas contra el esquema de la versión fijada y no crear claves alternativas traducidas. Si una opción no está disponible o no aplica, no mostrar un control activo sin efecto.

No inferir configuración no representada: «Soportes: No» no decide tipo de soporte, umbral ni interfaces; abrir detalle para esas opciones. Impresora, boquilla y material son resúmenes de los valores reales del proyecto.

### 7.2 Flujo de escritura

1. Leer el valor efectivo mediante los resolutores actuales y el esquema.
2. Mantener un borrador textual local mientras se edita.
3. Aceptar coma decimal española y punto; no aplicar sustituciones a campos de G-code o texto libre.
4. Validar tipo, unidad, límites y dependencias del esquema.
5. Confirmar con Enter, salida del campo o botón visible. Ante valor inválido, explicar y conservar el borrador; no escribir `NaN`, vacío ni un valor parcialmente tecleado al motor.
6. Escribir por el setter del ámbito activo con actualización funcional.
7. Dejar la invalidación y eventual relaminado a las rutas existentes.

Un campo sin override hereda. Borrar un override significa eliminar su clave, no reemplazarla arbitrariamente por el default del esquema.

### 7.3 Ámbito global y por placa

Cuando haya varias placas, mostrar «Global / Placa N». Reutilizar la proyección de `ProcessCard` y los metadatos de `processPanel` para que Rápido y Avanzado reciban los mismos ajustes efectivos y setter.

Marcar los valores sobrescritos y ofrecer «Heredar valor global». En materiales con varias herramientas, conservar la proyección del extrusor seleccionado: no sobrescribir todas las entradas de un vector al modificar una sola.

La selección de un objeto no debe cambiar silenciosamente el ámbito del formulario. Ajustes por objeto o por intervalo Z solo pueden incorporarse como capacidad adicional tras verificar el modelo de datos, el motor y la exportación. La presencia de una opción en el esquema no demuestra por sí sola que el visor admita ese ámbito.

### 7.4 Formulario avanzado

- Conservar el esquema, `uiTree`, reglas de habilitación y widgets especializados.
- Categorías legibles: Calidad, Resistencia, Velocidad, Soportes, Multimaterial y Otras, sujetas al árbol real y a la tecnología.
- «Avanzado» es el acceso a la configuración completa disponible; dentro se puede conservar el filtro de nivel existente. No equiparar accidentalmente el acceso al valor interno `advanced` si eso oculta opciones Expert.
- Buscador por etiqueta, clave y categorías; traducciones como presentación, claves originales como identidad.
- Mantener búsqueda, categoría, nivel y scroll al recoger el inspector y cambiar de orientación.
- Cada opción incluye unidad, ayuda táctil, estado de modificación y motivo de deshabilitación cuando aplique.
- Mover referencias internas como `Tab.cpp:...` a un modo de desarrollo; no mostrarlas en el flujo normal.
- En código o textos largos, abrir un editor ampliado que conserve valor y posición del cursor.

Conservar soporte FFF/SLA: un proyecto SLA muestra resina, exposición y controles correspondientes; no ofrecer relleno/paredes FFF como controles universales.

## 8. Herramientas, selección y transformaciones

### Herramientas principales

En móvil, mostrar Mover, Girar y Escalar para la selección actual; acceso «Más» a las otras operaciones disponibles. Si no hay selección, ofrecer selección/lista/añadir y ayudas de cámara. En tablet, presentar la misma colección como columna lateral. Utilizar un registro común de acciones y condiciones para evitar diferencias funcionales entre variantes.

Toda acción relevante debe tener nombre accesible y explicación de indisponibilidad. Pintura y transformación son modos excluyentes; activar una termina limpiamente la otra y retira su captura del puntero.

### Edición numérica precisa

Añadir o adaptar un editor de transformación dentro del controlador:

- Mover: coordenadas X/Y/Z en mm, e incrementos configurables de 0,1 / 1 / 10 mm.
- Girar: grados e incrementos de 1 / 15 / 90 grados.
- Escalar: porcentajes, dimensiones resultantes y bloqueo de proporciones.
- Selección múltiple: indicar explícitamente el pivote y si el valor es absoluto o relativo.

Resolver el sistema de coordenadas con el motor y la escena reales. No confundir el eje vertical de render con el Z físico de impresión. Transformar mediante las rutas actuales de geometría, límites, invalidación e historial, no manipulando un mesh por fuera del controlador.

Al iniciar un gesto, capturar una instantánea; durante el gesto, previsualizar; al finalizar, registrar una única operación de historial. Escape/cancelación vuelve a la instantánea. No crear una entrada por cada `pointermove` o paso intermedio de un input.

El historial actual no abarca automáticamente todos los cambios de ajustes o pintura. Mantener esa frontera documentada; ampliar su alcance sería otro cambio funcional que exige implementación y pruebas propias.

## 9. Contrato de interacción táctil

| Contexto | Interacción | Resultado |
| --- | --- | --- |
| Preparar | Toque breve sin desplazamiento | Seleccionar objeto; fondo vacío deselecciona si no hay selección múltiple. |
| Preparar | Arrastre de un dedo sin coger un gizmo | Orbitar cámara, sin cambiar selección al comenzar. |
| Preparar | Arrastre sobre un manejador activo | Transformar; cámara bloqueada durante el gesto. |
| Preparar/Previsualizar | Dos dedos | Desplazar y acercar/alejar cámara. |
| Lista de objetos | Activar selección múltiple y tocar filas | Añadir/quitar de la selección sin Ctrl. |
| Pintura | Un dedo sobre modelo | Pintar con el modo y tamaño activos. |
| Pintura | Dos dedos | Navegar; nunca continuar pintando con el segundo dedo. |
| Panel inferior | Arrastrar tirador | Cambiar altura del panel. |
| Formulario | Deslizar contenido | Scroll exclusivo del formulario. |

### Arbitraje de gestos

Implementar una máquina de interacción con estados `idle`, `pendingTap`, `orbiting`, `transforming`, `painting` y `cameraMultiTouch`. Valores iniciales para calibración: toque ≤250 ms y desplazamiento <8 px CSS. Un toque se confirma al soltar, no al `pointerdown`, evitando selección accidental al orbitar.

No basta con cambiar `OrbitControls.touches`: el código propio de selección y pintura también recibe eventos. Mantener un registro de punteros y asignar un único dueño a cada gesto antes de ejecutar acciones mutables. Ajustar el orden de listeners o centralizar el arbitraje para que OrbitControls no arranque una operación que ya pertenece al gizmo o al pincel.

Si aparece un segundo dedo durante pintura, terminar la parte del trazo ya válida, suspender el pincel y pasar a cámara sin generar una marca en la nueva posición. Al volver a un dedo, esperar un nuevo contacto para reanudar pintura. La política equivalente durante transformación debe cancelar la transformación activa y restaurar su instantánea antes de entrar en navegación, evitando saltos.

En `pointercancel`, pérdida de captura, cambio de visibilidad o cierre de herramienta: liberar punteros, restaurar controles y cerrar la operación sin dejar `orbit.enabled = false`. Registrar/cancelar el historial según si la operación terminó o fue abortada.

Usar Pointer Events y `setPointerCapture` cuando proceda. Aplicar `touch-action: none` solo al área de escena y al tirador que gestiona arrastre, no a toda la aplicación. El formulario mantiene `touch-action: pan-y` y scroll normal. El lápiz usa pintura/selección con el mismo arbitraje; no hacer obligatoria la presión.

Los manejadores visibles del gizmo pueden conservar su tamaño gráfico, pero su área de detección debe ser suficientemente grande en píxeles de pantalla. Comprobar que el área ampliada no roba gestos destinados al objeto o a otro eje.

## 10. Laminado, resultados y exportación

### Estados visibles

| Estado | Acción principal | Vista previa |
| --- | --- | --- |
| Vacío | Importar/añadir un modelo. | Deshabilitada. |
| Modelo listo | Laminar. | Deshabilitada si no hay resultado vigente. |
| Laminando | Cancelar y progreso real si se conoce. | Según disponibilidad real de capas; sin inventar resultado final. |
| Resultado válido | Exportar como acción principal; Relaminar como secundaria. | Capas, estadísticas y leyenda disponibles. |
| Configuración/geometría cambiada | Laminar de nuevo. | Retirar resultado invalidado conforme a la lógica existente. |
| Error | Mensaje contextual y reintento cuando proceda. | No presentar un resultado fallido como válido. |
| G-code/SL1 importado | Exportación y controles que admite el artefacto. | Seguir las reglas específicas de importación actuales. |

No mostrar duración o gramos antes de disponer de datos reales. La compresión/exportación puede no proporcionar porcentaje: mostrar actividad indeterminada, nunca un temporizador que simule progreso.

Con varias placas, un menú accesible distingue «Laminar placa actual» y «Laminar todas». Mantener progreso y estado por placa. Conservar los límites de memoria y concurrencia existentes; abrir/cerrar paneles no debe iniciar otro worker.

Un resultado conserva su placa y revisión de configuración. Los cambios globales y por placa deben invalidar lo que corresponda mediante las rutas actuales; las excepciones de artefactos importados no se reemplazan con un indicador genérico `dirty`.

Si hay geometría fuera del volumen imprimible, mantener la advertencia y la política existente: puede permitirse laminar para inspeccionar el problema, pero la exportación bloqueada no se habilita por usar un botón móvil nuevo. Usar el mismo guard en todas las rutas de exportación.

### Inspector de capas

- Resumen de tiempo/material si el resultado los contiene.
- Número de capa visible con entrada directa y botones −/+.
- Slider principal de capa superior; ajuste de capa inferior en «Rango» para evitar dos tiradores diminutos superpuestos.
- Modo «Solo esta capa» y «Mostrar desplazamientos» cuando aplique.
- Selector de color por función, velocidad, altura, ancho, ventilador, temperatura o filamento según capacidad real.
- Leyenda plegable y navegación de movimientos dentro de la capa para FFF; no mostrar esa navegación como si una capa SLA tuviera el mismo orden de extrusión.

El motor conserva índices de capa desde cero y la interfaz muestra numeración desde uno: convertir exactamente en el borde UI. Mantener `0 ≤ lo ≤ hi < layerCount` y deshabilitar controles con cero capas. Agrupar actualizaciones del arrastre con `requestAnimationFrame` sin bloquear la interacción ni provocar un relaminado.

## 11. CSS, encapsulamiento y tamaño del canvas

### Tokens iniciales

Usar los tokens existentes del tema como fuente cuando haya equivalencia. Añadir únicamente los necesarios, dentro de ambos Shadow DOM cuando corresponda.

```css
/* NUEVO: ejemplo de tokens y reglas, sujeto a integración con el tema actual. */
:host {
  --rs-accent: #00b64a;
  --rs-primary-bg: #007f35;
  --rs-primary-fg: #ffffff;
  --rs-scene-bg: #161b20;
  --rs-panel-bg: #f4f6f8;
  --rs-card-bg: #ffffff;
  --rs-text: #18212b;
  --rs-muted: #526170;
  --rs-target: 48px;
  --rs-header: 56px;
  --rs-inspector: 320px;
  --rs-space: 16px;
}

* { box-sizing: border-box; }
.responsive-shell { min-width: 0; min-height: 0; overflow: hidden; }
.scene-surface { position: relative; min-width: 0; min-height: 0; }
.scene-surface canvas { display: block; width: 100%; height: 100%; }
.scene-input, .sheet-handle { touch-action: none; }
.inspector-scroll {
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior-y: contain;
  touch-action: pan-y;
}
button, input, select { min-height: var(--rs-target); }
input, select, textarea { font-size: 16px; }
.icon-button { min-width: var(--rs-target); }
.primary-button {
  min-height: 52px;
  background: var(--rs-primary-bg);
  color: var(--rs-primary-fg);
}
.mobile-navigation { padding-bottom: env(safe-area-inset-bottom, 0px); }
.app-header { padding-top: env(safe-area-inset-top, 0px); }

@media (prefers-reduced-motion: reduce) {
  .inspector-surface { transition: none; }
}
```

El verde vivo de las maquetas se conserva como acento. Para texto blanco sobre botón, usar una variante más oscura y verificar contraste; no asumir que blanco sobre el verde original pasa WCAG. El CSS anterior es una base de integración, no un reemplazo completo listo para copiar sobre el archivo actual.

### Distribución estable

Utilizar CSS Grid o Flex sobre una estructura de hijos estable. En compacto: cabecera → modo → escena → inspector → acción → navegación. En expandido: cabecera a todo el ancho; herramientas a la izquierda; escena central; inspector a la derecha; acción en el pie derecho.

Calcular variantes en un hook propuesto `useResponsiveLayout` y reflejarlas mediante `data-layout`. Usar container queries para detalles puramente visuales cuando sean compatibles con la matriz objetivo; el comportamiento JS debe derivar de la misma medida y umbrales. Evitar dos fuentes que discrepen entre `window.innerWidth` y el contenedor real.

El contenedor de la integración necesita posición y altura reales, conforme al contrato actual del visor. Para una pantalla completa, usar `height: 100dvh` con fallback a `100vh`; para un slicer incrustado, respetar la altura que aporta el host y no ocupar toda la página por defecto.

### Resize y cámara

- Reutilizar el `ResizeObserver` de la escena; ampliar solo lo que falte.
- Actualizar dimensiones del renderer y relación de aspecto cuando cambie el área real.
- Evitar llamadas con ancho/alto cero y agrupar notificaciones por frame.
- Conservar posición, objetivo de cámara y selección al abrir paneles. No llamar a encuadrar todo en cada resize.
- En panel superpuesto, impedir interacción con el fondo y ofrecer encuadre útil al volver; no utilizar coordenadas de un elemento distinto para el raycast.
- El cambio de variante no recrea renderer, geometrías, materiales ni workers.

## 12. Teclado virtual, foco y accesibilidad

El teclado virtual puede reducir el visual viewport sin modificar igual el layout viewport en todos los navegadores. Observar `window.visualViewport` cuando exista; tratar su ausencia con el comportamiento normal del navegador. No interpretar cualquier cambio de altura como apertura del teclado sin comprobar que hay un campo editable enfocado.

Con un campo activo: asegurar que quede visible dentro del scroll del inspector, mantener disponible confirmar/cerrar y evitar que la barra de acción tape el campo. Tras cerrar el teclado, restaurar la posición preferida del panel y su scroll. Limpiar todos los listeners al desmontar.

Requisitos de accesibilidad:

- Etiquetas visibles y nombres accesibles para botones e inputs; `title` no basta.
- Estados seleccionados mediante `aria-selected`/`aria-pressed` según semántica.
- Tabs con asociación a su panel; herramientas como botones, no como pestañas ficticias.
- Foco visible sobre fondos claros y oscuros; orden de tabulación coherente con el orden visual.
- Contraste WCAG 2.2 AA: 4,5:1 en texto normal y 3:1 donde corresponda a texto grande/controles.
- Información que no dependa solo del verde, opacidad o posición.
- Progreso anunciado de forma moderada con `aria-live="polite"`; errores con un anuncio adecuado, sin repetir cada frame.
- Panel inferior no modal cuando permite seguir usando la escena; no bloquear el foco en ese estado.
- Diálogos superpuestos modales con nombre, cierre visible, foco inicial, ciclo de foco y devolución al disparador. Aplicar bloqueo al fondo correspondiente también dentro del Shadow DOM.
- Ayuda de valores deshabilitados y de Capas accesible por foco o un control informativo, aunque el botón de acción esté deshabilitado.
- Aumento de texto y zoom sin perder campos o acciones; en tamaños extremos, priorizar un formulario de una columna y scroll utilizable sobre la composición simultánea.

Al resolver el foco dentro de Shadow DOM, tener en cuenta `shadowRoot.activeElement`; `document.activeElement` puede señalar solo al host. Evitar atajos que se ejecuten mientras se escribe en un input, editor o diálogo.

## 13. Rendimiento y recuperación

Objetivos iniciales medibles, no promesas de capacidad universal:

- Mover/recoger el panel no inicia laminado ni altera `settings`.
- No reconstruir la escena durante cambios de presentación.
- Mantener el render bajo demanda existente y agrupar actualizaciones táctiles.
- Medir FPS y latencia con modelos pequeños y grandes; usar 30 FPS sostenidos como primer objetivo de interacción en el móvil de referencia, documentando modelo, dispositivo y navegador.
- Evitar enviar grandes arrays de geometría o capas al estado React de presentación.
- Cargar secciones avanzadas cuando se necesiten y no montar todas sus opciones por duplicado.
- Mantener el presupuesto de memoria, cancelación y fallback del motor. Un ancho pequeño no permite inferir RAM disponible.
- Si se introduce un límite de pixel ratio, hacerlo configurable y limitado al render: no debe cambiar la resolución ni los parámetros del laminado.
- Mostrar un estado útil ante WebGL no disponible o pérdida de contexto. No ocultar errores dentro de una pantalla vacía.

La retención en memoria durante rotación no implica recuperación tras cierre o recarga. Para esa necesidad, añadir posteriormente guardado de proyecto con una política explícita y verificada; no prometer autoguardado por haber persistido unas preferencias de interfaz.

## 14. Archivos y cambios previstos

Rutas relativas al paquete del visor. Los archivos nuevos son orientativos y pueden ajustarse a las convenciones del repositorio.

| Archivo | Trabajo |
| --- | --- |
| `src/Viewport.jsx` | Conectar layout, controladores y superficies sin desmontar la escena. |
| `styles.css` | Distribuciones, superficies, tokens, tamaños táctiles y accesibilidad visual. |
| `src/hooks/use_responsive_layout.js` — nuevo | Medición de contenedor y altura útil; variante derivada. |
| `src/hooks/use_responsive_ui.js` — nuevo | Estado/transiciones de inspector y navegación. |
| `src/ui/ResponsiveShell.jsx` — nuevo | Estructura estable de distribución. |
| `src/ui/InspectorSurface.jsx` — nuevo | Panel inferior/lateral, scroll y modalidad. |
| `src/ui/MobileNavigation.jsx` — nuevo | Modelo/Ajustes/Capas y sincronización del modo. |
| `src/ui/QuickSettings.jsx` — nuevo | Controles rápidos ligados al esquema y ámbito. |
| `src/ui/TopBar.jsx` | Cabecera y menú adaptable; semántica abrir/añadir. |
| `src/ui/GizmoRail.jsx`, `ObjectToolbar.jsx` | Registro/presentación de herramientas y acciones secundarias. |
| `src/ui/ObjectList.jsx`, `PlateBar.jsx` | Selección múltiple táctil y navegación de placas. |
| `src/ui/ProcessCard.jsx`, `ScopeToggle.jsx` | Ámbito compartido, indicadores y acceso Rápido/Avanzado. |
| `src/ui/PrinterCard.jsx`, `FilamentCard.jsx`, `ResinCard.jsx` | Resúmenes compactos y editores táctiles sin perder alcance. |
| `src/components/SettingsPanel.jsx` | Control de búsqueda/categorías/nivel cuando sea necesario y widgets con borrador/validación. |
| `src/components/styles.css` | Adaptación del segundo Shadow DOM y ocultación de metadatos de desarrollo. |
| `src/ui/PreviewControls.jsx`, `StatsCard.jsx`, `MoveBar.jsx` | Capas, controles precisos, leyenda y estados por tecnología. |
| `src/ui/SliceBar.jsx` | Acción adaptable, progreso/cancelación y exportación con los mismos guards. |
| `src/scene/use_three_scene.js`, `paint_input.js` | Arbitraje de punteros, captura, cancelación y continuidad de cámara. |
| `types/viewer.d.ts`, documentación | Tipar solo los contratos públicos añadidos y actualizar ejemplos. |

Evitar modificar las fuentes del kernel por razones de maquetación. Los wrappers AGPL que inyectan catálogo y motor siguen consumiendo el visor con los mismos contratos. Revisar las instrucciones del repositorio antes de editar y ejecutar su comprobación completa exigida para la versión fijada.

## 15. Secuencia de implementación

### Fase 1 — Conservar comportamiento y crear la estructura

Fijar versiones, capturar comportamiento actual e identificar dependencias de la escena. Extraer `ResponsiveShell` y el estado de presentación. Reorganizar inicialmente en ancho expandido, demostrando que importar, transformar, laminar y exportar conservan su comportamiento.

### Fase 2 — Distribuciones y paneles

Implementar medición, variantes, pies de acción y panel inferior/lateral. Verificar resize sin remontajes ni pérdida de cámara. Resolver orientación horizontal corta y teclado virtual antes de añadir detalles visuales.

### Fase 3 — Configuración

Incorporar resúmenes, Rápido/Avanzado, validación y persistencia de búsqueda. Probar global/placa y proyección por extrusor con valores realmente distintos para detectar escrituras en el ámbito equivocado.

### Fase 4 — Tacto

Centralizar arbitraje de gestos; adaptar selección múltiple, transformaciones y pintura. Calibrar umbrales y manejadores con dispositivos reales y confirmar que el ratón no pierde funciones.

### Fase 5 — Resultados y robustez

Adaptar capas, leyendas, estadísticas, cancelación, errores y exportación. Comprobar placas múltiples y artefactos importados, incluidos los límites FFF/SLA.

### Fase 6 — Validación y entrega

Pruebas funcionales, accesibilidad, rendimiento y regresión de escritorio. Documentar diferencias respecto a las maquetas y límites pendientes. No declarar terminada la adaptación solo porque una captura estática se vea bien.

## 16. Criterios de aceptación verificables

### Distribución

- [ ] A 360×800, 390×844 y 430×932 px, los controles esenciales no desbordan horizontalmente.
- [ ] A 768×1024 y 820×1180 px, el panel intermedio deja una vía clara de volver al visor.
- [ ] A 1024×768 y 1180×820 px, visor e inspector pueden usarse simultáneamente.
- [ ] A 844×390 px se activa una composición de poca altura utilizable.
- [ ] La anchura de un slicer incrustado, no la ventana completa, determina la variante.
- [ ] Rotar varias veces conserva cámara, objetos, selección, placas, pintura y configuración.
- [ ] Solo existe una instancia de renderer y no se crean workers por abrir paneles.

### Interacción y configuración

- [ ] Orbitar con un dedo no cambia accidentalmente la selección.
- [ ] Pellizcar/desplazar no pinta, transforma ni arrastra el panel.
- [ ] Cancelar/perder un puntero no deja la cámara bloqueada.
- [ ] Selección múltiple, duplicar, borrar, apoyar y otras acciones existentes tienen acceso táctil.
- [ ] Una transformación produce una operación de historial, no una por frame.
- [ ] `0,20` y `0.20` generan el mismo valor numérico válido donde corresponde.
- [ ] Una entrada inválida no llega a `settings` ni inicia un laminado.
- [ ] Rápido y Avanzado muestran el mismo valor efectivo.
- [ ] Editar Placa 2 no altera Global ni Placa 1; «Heredar» elimina el override correcto.
- [ ] Modificar un filamento seleccionado no cambia los demás extrusores.
- [ ] Cambiar panel, categoría o búsqueda no invalida el resultado.

### Laminado y exportación

- [ ] Progreso, cancelación y reintento reflejan operaciones reales.
- [ ] Capas se habilita solo cuando hay datos disponibles para la placa actual.
- [ ] La numeración visible de capas coincide con los índices internos convertidos.
- [ ] Cambiar un parámetro invalida los resultados que corresponde; no quedan estadísticas antiguas presentadas como vigentes.
- [ ] Un modelo fuera de cama conserva la advertencia y las restricciones de exportación existentes.
- [ ] Abrir y añadir tienen la semántica indicada, sin pérdida silenciosa de trabajo.
- [ ] Proyecto 3MF, G-code y SL1 conservan las rutas y capacidades que admite la versión base.
- [ ] FFF/SLA no muestran controles de una tecnología como si aplicasen a la otra.

### Accesibilidad y dispositivos

- [ ] Acciones y campos utilizables con teclado y lector de pantalla.
- [ ] Foco/restauración correctos en diálogo, ayuda, panel y Shadow DOM.
- [ ] Contraste comprobado, incluido el texto de los botones verdes.
- [ ] Texto ampliado y contenido largo no ocultan acciones imprescindibles.
- [ ] Teclado virtual no tapa el campo ni provoca pérdida del borrador.
- [ ] Validación en Android Chrome y Safari iPadOS; regresión con ratón/teclado en escritorio.
- [ ] Como referencia práctica, incluir el moto g73 del usuario si está disponible; registrar versión de navegador y modelo de prueba.

### Estrategia de pruebas

Añadir pruebas de integración para los riesgos nuevos: cambio de variante sin desmontaje, ámbitos, validación, arbitraje de punteros y estado de resultados. Usar pruebas puras para conversiones o transiciones con casos límite reales. Las capturas comparativas verifican apariencia, pero no sustituyen la interacción táctil ni los tests del proyecto.

Los checks de esta sección son requisitos pendientes para la futura implementación; no se han ejecutado sobre una interfaz modificada en este encargo, que entrega una especificación.

## 17. Entregables del desarrollo

1. Cambios en el visor y estilos con API existente compatible.
2. Componentes responsive y contratos internos tipados/documentados.
3. Matriz de comportamiento por ancho, altura y tecnología.
4. Pruebas apropiadas y evidencias de móvil, tablet y escritorio.
5. Lista de limitaciones que ya existían y de nuevas capacidades implementadas, sin atribuir al diseño funciones del motor no comprobadas.

## 18. Fuentes técnicas de referencia

- Repositorio canónico: https://github.com/kimgh06/Three_Slicer
- Documentación del visor: https://github.com/kimgh06/three-slicer-viewer/blob/b3ab1b9183278d103b7ddbdcee3198036174bf2e/VIEWER.md
- Contratos públicos: https://github.com/kimgh06/three-slicer-viewer/blob/b3ab1b9183278d103b7ddbdcee3198036174bf2e/types/viewer.d.ts
- Composición del visor: https://github.com/kimgh06/three-slicer-viewer/blob/b3ab1b9183278d103b7ddbdcee3198036174bf2e/src/Viewport.jsx
- Estilos actuales: https://github.com/kimgh06/three-slicer-viewer/blob/b3ab1b9183278d103b7ddbdcee3198036174bf2e/styles.css
- Formulario de ajustes: https://github.com/kimgh06/three-slicer-viewer/blob/b3ab1b9183278d103b7ddbdcee3198036174bf2e/src/components/SettingsPanel.jsx
- Ámbitos del proceso: https://github.com/kimgh06/three-slicer-viewer/blob/b3ab1b9183278d103b7ddbdcee3198036174bf2e/src/ui/ProcessCard.jsx
- Escena e interacción: https://github.com/kimgh06/three-slicer-viewer/blob/b3ab1b9183278d103b7ddbdcee3198036174bf2e/src/scene/use_three_scene.js
- Laminado/exportación: https://github.com/kimgh06/three-slicer-viewer/blob/b3ab1b9183278d103b7ddbdcee3198036174bf2e/src/ui/SliceBar.jsx
- Controles de capas: https://github.com/kimgh06/three-slicer-viewer/blob/b3ab1b9183278d103b7ddbdcee3198036174bf2e/src/ui/PreviewControls.jsx

La inspección de código fundamenta las observaciones sobre el estado actual. Los componentes nuevos, dimensiones, umbrales táctiles, objetivos de rendimiento y organización propuestos son decisiones de diseño de esta especificación y deben validarse durante su implementación.
