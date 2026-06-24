import 'package:flutter/material.dart';

/// Jobify warm-paper color tokens — light and dark variants.
///
/// Each semantic role has a `*Light` and `*Dark` constant. `buildTheme`
/// picks the appropriate pair via its isDark branch.
abstract final class JobifyColors {
  // ── Paper surfaces ──────────────────────────────────────────────────────
  static const paperLight = Color(0xFFF4EFE3);
  static const paperDark = Color(0xFF0D110E);

  static const paper2Light = Color(0xFFECE4D3);
  static const paper2Dark = Color(0xFF080B09);

  static const paper3Light = Color(0xFFE4DAC4);
  static const paper3Dark = Color(0xFF1A201A);

  static const panelLight = Color(0xFFFAF7EF);
  static const panelDark = Color(0xFF121712);

  // ── Ink (text / icon) ───────────────────────────────────────────────────
  static const inkLight = Color(0xFF221C16);
  static const inkDark = Color(0xFFE9E4D6);

  static const inkSoftLight = Color(0xFF6C6354);
  static const inkSoftDark = Color(0xFFB7B2A3);

  static const inkFaintLight = Color(0xFF9B917E);
  static const inkFaintDark = Color(0xFF6F7868);

  // ── Lines / dividers ────────────────────────────────────────────────────
  static const lineLight = Color(0xFFD9CFB9);
  static const lineDark = Color(0xFF232B23);

  static const lineStrongLight = Color(0xFFC4B89C);
  static const lineStrongDark = Color(0xFF34402F);

  // ── Brand blue ──────────────────────────────────────────────────────────
  static const brandBlueLight = Color(0xFF0048A8);
  static const brandBlueDark = Color(0xFF4F8CFF);

  static const brandBlueDeepLight = Color(0xFF003C8F);
  static const brandBlueDeepDark = Color(0xFF2F6FE0);

  static const brandBlueTintLight = Color(0xFFE1ECF8);
  static const brandBlueTintDark = Color(0xFF16243F);

  // ── Accent (terracotta / coral) ─────────────────────────────────────────
  static const accentLight = Color(0xFFD8472A);
  static const accentDark = Color(0xFFFF6A48);

  static const accentDeepLight = Color(0xFFB23A20);
  static const accentDeepDark = Color(0xFFD8472A);

  static const accentWashLight = Color(0xFFF3D9CF);
  static const accentWashDark = Color(0xFF3A1C14);

  static const accentInkLight = Color(0xFFFFFFFF);
  static const accentInkDark = Color(0xFF1A0F0A);

  // ── Forest (success / positive) ─────────────────────────────────────────
  static const forestLight = Color(0xFF1F4034);
  static const forestDark = Color(0xFF6FDC8C);

  static const forestSoftLight = Color(0xFFCFDCD2);
  static const forestSoftDark = Color(0xFF143020);

  // ── Gold ────────────────────────────────────────────────────────────────
  static const goldLight = Color(0xFFB8842F);
  static const goldDark = Color(0xFFFFB000);

  // ── Danger / error ──────────────────────────────────────────────────────
  static const dangerLight = Color(0xFFB23A20);
  static const dangerDark = Color(0xFFFF5D49);

  // ── Semantic aliases (brightness-agnostic, used in build_theme) ─────────
  static const error = dangerLight; // light fallback; build_theme overrides
  static const onError = Color(0xFFFFFFFF);

  // ── Score bands — product semantics, not chrome ─────────────────────────
  /// `total_score < 0.65`
  static const scoreLow = Color(0xFFCF8A1D);

  /// `0.65 <= total_score < 0.80`
  static const scoreMid = Color(0xFF0048A8); // brand blue for consistency

  /// `total_score >= 0.80`
  static const scoreHigh = Color(0xFF1E8A4F);
}
