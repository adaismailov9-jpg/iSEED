import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MIN_POINTS, midpoint } from '../lib/geo';
import KYRGYZSTAN from '../data/kyrgyzstan.json';

// Only Kyrgyzstan: everything else is covered by a cream mask, and the map cannot be moved far away.
const WORLD = [[-89, -179], [-89, 179], [89, 179], [89, -179]];
const KG_OUTLINES = KYRGYZSTAN.polygons.map(([outer]) => outer);
const ENCLAVES = KYRGYZSTAN.polygons.flatMap(([, ...holes]) => holes); // neighbours' enclaves inside Kyrgyzstan
const KG_BOUNDS = L.latLngBounds(KG_OUTLINES.flat());
const MASK = { stroke: false, fillColor: '#f7f4ea', fillOpacity: 0.88, interactive: false };
const BORDER = { color: '#2f4b2a', weight: 2.5, fill: false, interactive: false };

// The two map backgrounds the farmer can switch between.
const BASEMAPS = {
  satellite: { url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attribution: 'Imagery © Esri' },
  map: { url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', attribution: '© OpenStreetMap' },
};
const CORNER = L.divIcon({ className: 'corner', iconSize: [22, 22] });
const EDGE_DOT = L.divIcon({ className: 'edge-dot', iconSize: [16, 16] });
const STYLE = { color: '#ffd43b', weight: 3, fillOpacity: 0.2 };

// Field editor:
// - tap an empty map → onTapEmpty(position) places a field there;
// - drag a corner to move it, tap a corner to remove it (if more than 4);
// - drag the dot in the middle of an edge to add a new corner there.
// onMove(points) fires during a drag (for the live area), onChange(points) when it ends.
export default function FieldMap({ points, onChange, onMove, onTapEmpty, focus, basemap }) {
  const boxRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const latest = useRef(null); // latest props, read inside Leaflet event handlers
  latest.current = { points, onChange, onMove, onTapEmpty };

  // Create the map once.
  useEffect(() => {
    const map = L.map(boxRef.current, { zoomControl: false, minZoom: 6, maxBounds: KG_BOUNDS.pad(0.15), maxBoundsViscosity: 1 });
    map.fitBounds(KG_BOUNDS);
    map.attributionControl.setPrefix(false); // hide the "Leaflet" label with the flag, keep the map credits
    L.control.zoom({ position: 'bottomright' }).addTo(map);

    L.polygon([WORLD, ...KG_OUTLINES], MASK).addTo(map);
    L.polygon(ENCLAVES, MASK).addTo(map);
    L.polygon(KYRGYZSTAN.polygons, BORDER).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);

    map.on('click', (e) => {
      if (latest.current.points.length === 0) latest.current.onTapEmpty([e.latlng.lat, e.latlng.lng]);
    });

    if (latest.current.points.length) map.fitBounds(latest.current.points, { padding: [60, 60], maxZoom: 17 });
    mapRef.current = map;
    return () => map.remove();
  }, []);

  // Show the chosen background: satellite or ordinary map.
  useEffect(() => {
    const { url, attribution } = BASEMAPS[basemap];
    const tiles = L.tileLayer(url, { maxZoom: 19, attribution }).addTo(mapRef.current);
    return () => tiles.remove();
  }, [basemap]);

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
