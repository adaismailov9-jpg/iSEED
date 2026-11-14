import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MIN_POINTS, midpoint } from '../lib/geo';

const IMAGERY = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
const CORNER = L.divIcon({ className: 'corner', iconSize: [22, 22] });
const EDGE_DOT = L.divIcon({ className: 'edge-dot', iconSize: [16, 16] });
const STYLE = { color: '#ffd43b', weight: 3, fillOpacity: 0.2 };

// Field editor:
// - tap an empty map → onTapEmpty(position) places a field there;
// - drag a corner to move it, tap a corner to remove it (if more than 4);
// - drag the dot in the middle of an edge to add a new corner there.
// onMove(points) fires during a drag (for the live area), onChange(points) when it ends.
export default function FieldMap({ points, onChange, onMove, onTapEmpty, focus }) {
  const boxRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const latest = useRef(null); // latest props, read inside Leaflet event handlers
  latest.current = { points, onChange, onMove, onTapEmpty };

  // Create the map once.
  useEffect(() => {
    const map = L.map(boxRef.current, { zoomControl: false }).setView([41.5, 74.5], 7); // all of Kyrgyzstan
    L.tileLayer(IMAGERY, { maxZoom: 19, attribution: 'Imagery © Esri' }).addTo(map);
    map.attributionControl.setPrefix(false); // hide the "Leaflet" label with the flag, keep the Esri credit
    L.control.zoom({ position: 'bottomright' }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);

    map.on('click', (e) => {
      if (latest.current.points.length === 0) latest.current.onTapEmpty([e.latlng.lat, e.latlng.lng]);
    });

    if (latest.current.points.length) map.fitBounds(latest.current.points, { padding: [60, 60], maxZoom: 17 });
    mapRef.current = map;
    return () => map.remove();
  }, []);

  // Redraw the field when the corners change.
  useEffect(() => {
    const layer = layerRef.current;
    layer.clearLayers();
    if (points.length === 0) return;
    const shape = L.polygon(points, STYLE).addTo(layer);

    // A draggable handle. pointsAt(position) returns the corner list for where the handle is now.
    function addHandle(position, icon, pointsAt) {
      const marker = L.marker(position, { icon, draggable: true }).addTo(layer);
      const current = () => pointsAt([marker.getLatLng().lat, marker.getLatLng().lng]);
      marker.on('drag', () => {
        shape.setLatLngs(current());
        latest.current.onMove(current());
      });
      marker.on('dragend', () => latest.current.onChange(current()));
      return marker;
    }

    points.forEach((corner, i) => {
      const marker = addHandle(corner, CORNER, (pos) => points.map((p, j) => (j === i ? pos : p)));
      marker.on('click', () => {
        if (points.length > MIN_POINTS) latest.current.onChange(points.filter((_, j) => j !== i));
      });
    });

    points.forEach((corner, i) => {
      const next = points[(i + 1) % points.length];
      addHandle(midpoint(corner, next), EDGE_DOT, (pos) => [...points.slice(0, i + 1), pos, ...points.slice(i + 1)]);
    });
  }, [points]);

  useEffect(() => {
    if (focus) mapRef.current.setView(focus.center, focus.zoom);
  }, [focus]);

  return <div ref={boxRef} className="map" />;
}
