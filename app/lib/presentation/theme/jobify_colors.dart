import 'package:flutter/material.dart';

/// Jobify "Clear Sky" color tokens — light and dark variants.
///
/// Color is rationed: only `brandBlue*` (the match / primary action) and
/// `caveat*` (the honest weakness) carry meaning. Everything else is ink on a
/// cool sky surface. `buildTheme` picks the light/dark pair via its isDark flag.
abstract final class JobifyColors {
  // ── Sky surfaces ────────────────────────────────────────────────────────
  static const paperLight = Color(0xFFF4F6F9);
  static const paperDark = Color(0xFF0B1620);

  static const paper2Light = Color(0xFFEAEEF4);
  static const paper2Dark = Color(0xFF0F1C28);

  static const paper3Light = Color(0xFFDFE5EE);
  static const paper3Dark = Color(0xFF0A141D);

  static const panelLight = Color(0xFFFFFFFF);
  static const panelDark = Color(0xFF13212E);

  // ── Ink (text / icon) ───────────────────────────────────────────────────
  static const inkLight = Color(0xFF0F2440);
  static const inkDark = Color(0xFFE8EDF3);

  static const inkSoftLight = Color(0xFF5C6B7E);
  static const inkSoftDark = Color(0xFF9DB0C2);

  static const inkFaintLight = Color(0xFF94A1B2);
  static const inkFaintDark = Color(0xFF5E7186);

  // ── Lines / dividers ────────────────────────────────────────────────────
  static const lineLight = Color(0xFFE3E8EF);
  static const lineDark = Color(0xFF1E2D3B);

  static const lineStrongLight = Color(0xFFCED7E2);
  static const lineStrongDark = Color(0xFF2C3F50);

  // ── Brand blue — the one meaning color (the match + primary action) ──────
  static const brandBlueLight = Color(0xFF0048A8);
  static const brandBlueDark = Color(0xFF5B9BFF);

  static const brandBlueDeepLight = Color(0xFF00367D);
  static const brandBlueDeepDark = Color(0xFF3F86F5);

  static const brandBlueTintLight = Color(0xFFE7EEF8); // wash behind a match
  static const brandBlueTintDark = Color(0xFF13294A);

  static const brandInkLight = Color(0xFFFFFFFF); // text/icon on brand fill
  static const brandInkDark = Color(0xFF04101F);

  // ── Caveat amber — the honest weakness, only ────────────────────────────
  static const caveatLight = Color(0xFFC77A1E);
  static const caveatDark = Color(0xFFE0A24A);

  static const caveatWashLight = Color(0xFFFBF0E0);
  static const caveatWashDark = Color(0xFF2A1F0E);

  static const caveatInkLight = Color(0xFFFFFFFF);
  static const caveatInkDark = Color(0xFF1F1404);

  // ── Danger / error ──────────────────────────────────────────────────────
  static const dangerLight = Color(0xFFC0362B);
  static const dangerDark = Color(0xFFFF6A5A);
}
