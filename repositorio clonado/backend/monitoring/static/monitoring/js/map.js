function initLocationPicker(options) {
  const canvas = document.getElementById("map-canvas");
  if (!canvas) return;

  const latInput = document.getElementById(options.latInputId);
  const lngInput = document.getElementById(options.lngInputId);

  const hasInitial = options.initialLat !== null && options.initialLng !== null;
  const center = hasInitial
    ? { lat: options.initialLat, lng: options.initialLng }
    : { lat: 0, lng: 0 };

  const map = new google.maps.Map(canvas, {
    center: center,
    zoom: hasInitial ? 14 : 2,
  });

  const icon = options.iconUrl
    ? {
        url: options.iconUrl,
        scaledSize: new google.maps.Size(40, 40),
        anchor: new google.maps.Point(20, 20),
      }
    : undefined;

  let marker = null;

  function placeMarker(position) {
    if (marker) {
      marker.setPosition(position);
    } else {
      marker = new google.maps.Marker({
        position: position,
        map: map,
        draggable: true,
        icon: icon,
      });
      marker.addListener("dragend", () => {
        const pos = marker.getPosition();
        latInput.value = pos.lat();
        lngInput.value = pos.lng();
      });
    }
    latInput.value = position.lat;
    lngInput.value = position.lng;
  }

  if (hasInitial) {
    placeMarker(center);
  }

  map.addListener("click", (event) => {
    placeMarker({ lat: event.latLng.lat(), lng: event.latLng.lng() });
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function buildMarkerInfoContent(m) {
  let rows = "";
  if (m.sensors && m.sensors.length) {
    rows = m.sensors
      .map((s) => {
        const value = s.value === null || s.value === undefined ? "sin datos" : `${s.value} ${s.unit || ""}`.trim();
        return `<tr><td>${escapeHtml(s.variable)}</td><td>${escapeHtml(value)}</td></tr>`;
      })
      .join("");
  } else if (m.manual_entries && m.manual_entries.length) {
    rows = m.manual_entries
      .map((e) => {
        const valueBit = e.value !== null && e.value !== undefined ? ` (${e.value} ${e.unit || ""})`.trim() : "";
        return `<tr><td colspan="2">${escapeHtml(e.created_at)}${escapeHtml(valueBit)}<br>${escapeHtml(e.note)}</td></tr>`;
      })
      .join("");
  } else {
    rows = '<tr><td colspan="2">Sin datos todavía</td></tr>';
  }

  const metaBits = [escapeHtml(m.slug || m.product_type || "")];
  if (m.owner) metaBits.push(`Propietario: ${escapeHtml(m.owner)}`);

  return `
    <div class="map-info-window">
      <strong>${escapeHtml(m.name)}</strong><br>
      <span class="map-info-meta">${metaBits.join(" · ")}</span>
      <table class="map-info-table">${rows}</table>
    </div>
  `;
}

function initDevicesMap() {
  const canvas = document.getElementById("map-canvas");
  if (!canvas) return;

  const markers = JSON.parse(canvas.dataset.markers || "[]");
  const map = new google.maps.Map(canvas, {
    center: { lat: 0, lng: 0 },
    zoom: 2,
  });

  if (markers.length === 0) return;

  const bounds = new google.maps.LatLngBounds();
  const infoWindow = new google.maps.InfoWindow();

  markers.forEach((m) => {
    const position = { lat: m.lat, lng: m.lng };
    const icon = m.icon_url
      ? {
          url: m.icon_url,
          scaledSize: new google.maps.Size(40, 40),
          anchor: new google.maps.Point(20, 20),
        }
      : undefined;
    const marker = new google.maps.Marker({
      position: position,
      map: map,
      title: m.name,
      icon: icon,
    });
    marker.addListener("click", () => {
      infoWindow.setContent(buildMarkerInfoContent(m));
      infoWindow.open(map, marker);
    });
    bounds.extend(position);
  });

  if (markers.length === 1) {
    map.setCenter(bounds.getCenter());
    map.setZoom(14);
  } else {
    map.fitBounds(bounds);
  }
}
