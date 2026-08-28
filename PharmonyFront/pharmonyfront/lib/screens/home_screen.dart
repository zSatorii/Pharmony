// lib/screens/home_screen.dart
// HomeScreen Flutter — Replica fiel del home.html de Pharmony.

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';

const String kBaseUrl = 'http://localhost:8000';

class _C {
  static const brandDark    = Color(0xFF031438);
  static const brandDeep    = Color(0xFF052060);
  static const brandNavy    = Color(0xFF0A3A8C);
  static const brandMain    = Color(0xFF0D47C9);
  static const brandMid     = Color(0xFF1A5FD4);
  static const brandElec    = Color(0xFF2563EB);
  static const brandLight   = Color(0xFF3B82F6);
  static const brandCyan    = Color(0xFF06B6D4);
  static const brandSoft    = Color(0xFF93C5FD);
  static const brandPale    = Color(0xFFE0F2FE);
  static const surface0     = Color(0xFFF8FAFC);
  static const surface1     = Color(0xFFF1F5F9);
  static const surface2     = Color(0xFFE2E8F0);
  static const textMain     = Color(0xFF1E293B);
  static const textHeading  = Color(0xFF0F172A);
  static const textMuted    = Color(0xFF64748B);
  static const emerald      = Color(0xFF10B981);
  static const emeraldPale  = Color(0xFFECFDF5);
  static const amber        = Color(0xFFF59E0B);
  static const amberPale    = Color(0xFFFFFBEB);
  static const purple       = Color(0xFF7C3AED);
  static const purplePale   = Color(0xFFEDE9FE);
}

class Noticia {
  final int id; final String categoria, titulo, resumen, fecha, lectura, icono, link;
  final String? imageUrl, imageWebpUrl;
  Noticia({required this.id, required this.categoria, required this.titulo,
    required this.resumen, required this.fecha, required this.lectura,
    required this.icono, required this.link, this.imageUrl, this.imageWebpUrl});
  factory Noticia.fromJson(Map<String, dynamic> j) => Noticia(
    id: j['id'] ?? 0, categoria: j['categoria'] ?? '', titulo: j['titulo'] ?? '',
    resumen: j['resumen'] ?? '', fecha: j['fecha'] ?? '', lectura: j['lectura'] ?? '',
    icono: j['icono'] ?? '💊', link: j['link'] ?? '',
    imageUrl: (j['image_url'] as String?)?.isNotEmpty == true ? j['image_url'] : null,
    imageWebpUrl: (j['image_webp_url'] as String?)?.isNotEmpty == true ? j['image_webp_url'] : null,
  );
}

class Sede {
  final int id; final String nombre, ciudad, direccion, telefono, eps;
  Sede({required this.id, required this.nombre, required this.ciudad,
    required this.direccion, required this.telefono, required this.eps});
  factory Sede.fromJson(Map<String, dynamic> j) => Sede(
    id: j['id'] ?? 0, nombre: j['nombre'] ?? '', ciudad: j['ciudad'] ?? '',
    direccion: j['direccion'] ?? 'Direccion no especificada',
    telefono: j['telefono'] ?? '', eps: j['eps'] ?? 'Pharmony');
}

class HomeData {
  final List<Noticia> noticias; final Noticia? destacada; final List<Sede> sedes;
  HomeData({required this.noticias, required this.destacada, required this.sedes});
  factory HomeData.fromJson(Map<String, dynamic> j) {
    final n = (j['noticias'] as List? ?? []).map((x) => Noticia.fromJson(x)).toList();
    final s = (j['sedes'] as List? ?? []).map((x) => Sede.fromJson(x)).toList();
    return HomeData(noticias: n, sedes: s,
      destacada: j['noticia_destacada'] != null
        ? Noticia.fromJson(j['noticia_destacada'])
        : n.isNotEmpty ? n.first : null);
  }
}

class HomeService {
  static Future<HomeData> fetch() async {
    final res = await http.get(Uri.parse('$kBaseUrl/api/v1/inicio/'), headers: {'Accept': 'application/json'});
    if (res.statusCode != 200) throw Exception('Error ${res.statusCode}');
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    if (body['success'] != true) throw Exception('success=false');
    return HomeData.fromJson(body);
  }
}

class _HealthTab {
  final String label, title, desc, visualTitle, visualNote;
  final IconData tabIcon, visualIcon;
  final List<String> tips;
  const _HealthTab({required this.label, required this.tabIcon, required this.title,
    required this.desc, required this.tips, required this.visualTitle,
    required this.visualNote, required this.visualIcon});
}

const List<_HealthTab> _kTabs = [
  _HealthTab(label: 'Cadena de Frio', tabIcon: Icons.ac_unit_rounded, visualIcon: Icons.thermostat_rounded,
    title: 'Conservacion en Cadena de Frio',
    desc: 'Insulinas y vacunas requieren entre 2 y 8 grados C para mantener su eficacia.',
    tips: ['Guarda en estantes centrales del refrigerador, nunca en la puerta.',
           'Usa nevera portatil con geles refrigerantes para transportarlos.',
           'Si la insulina se congela, pierde su efecto y debe descartarse.'],
    visualTitle: 'Temperatura Ideal: 2 - 8 grados C', visualNote: 'Protege de luz solar y humedad.'),
  _HealthTab(label: 'Antibioticos', tabIcon: Icons.medication_rounded, visualIcon: Icons.shield_rounded,
    title: 'Uso Responsable de Antibioticos',
    desc: 'Los antibioticos combaten bacterias, no virus. Su mal uso genera superbacterias.',
    tips: ['Cumple los horarios y dias indicados por el medico.',
           'Nunca te automediques ni reutilices dosis sobrantes.',
           'No compartas antibioticos; cada caso requiere prescripcion individual.'],
    visualTitle: 'Previene la Resistencia Bacteriana', visualNote: 'Toma las dosis a la hora exacta.'),
  _HealthTab(label: 'Lectura de Recetas', tabIcon: Icons.description_rounded, visualIcon: Icons.fact_check_rounded,
    title: 'Como Leer y Validar tu Receta',
    desc: 'Una formula medica clara garantiza que recibas el principio activo correcto.',
    tips: ['Verifica nombre generico, concentracion, dosis y duracion.',
           'La mayoria de formulas tienen vigencia de 30 dias.',
           'Usa DocsIA en Pharmony para escanear y confirmar disponibilidad.'],
    visualTitle: 'Verificacion de Prescripcion', visualNote: 'Requiere firma y registro medico valido.'),
  _HealthTab(label: 'Puntos Azules', tabIcon: Icons.recycling_rounded, visualIcon: Icons.recycling_rounded,
    title: 'Desecho Seguro de Medicamentos',
    desc: 'Botar medicamentos vencidos al inodoro contamina rios y suelos.',
    tips: ['Deposita medicamentos vencidos en contenedores de Punto Azul.',
           'Destruye las etiquetas de las cajas para evitar falsificaciones.',
           'Nunca arrojes pastillas o liquidos por el desague.'],
    visualTitle: 'Compromiso Ambiental', visualNote: 'Lleva tus medicinas vencidas al Punto Azul.'),
];