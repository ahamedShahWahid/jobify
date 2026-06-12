import 'package:flutter/material.dart';

/// Jobify color tokens.
///
/// Placeholder values for v0 — replace when a designer enters the loop.
/// Bands map to ColorScheme slots in buildTheme.
abstract final class JobifyColors {
  // Brand
  static const indigo50 = Color(0xFFEEF0FF);
  static const indigo100 = Color(0xFFDDE2FF);
  static const indigo200 = Color(0xFFBAC4FF);
  static const indigo300 = Color(0xFF96A6FF);
  static const indigo400 = Color(0xFF7388FA);
  static const indigo500 = Color(0xFF5067E8);
  static const indigo600 = Color(0xFF3D52C6);
  static const indigo700 = Color(0xFF2E3EA0);
  static const indigo800 = Color(0xFF1F2C7A);
  static const indigo900 = Color(0xFF111A55);

  // Neutrals
  static const neutral0 = Color(0xFFFFFFFF);
  static const neutral50 = Color(0xFFF7F8FA);
  static const neutral100 = Color(0xFFEEEFF3);
  static const neutral200 = Color(0xFFD9DCE3);
  static const neutral300 = Color(0xFFB7BCC8);
  static const neutral400 = Color(0xFF8A91A1);
  static const neutral500 = Color(0xFF626878);
  static const neutral600 = Color(0xFF464B58);
  static const neutral700 = Color(0xFF2E323C);
  static const neutral800 = Color(0xFF1B1E26);
  static const neutral900 = Color(0xFF0E1015);

  // Score bands — product semantics, not chrome.
  /// `total_score < 0.65`
  static const scoreLow = Color(0xFFCF8A1D);

  /// `0.65 <= total_score < 0.80`
  static const scoreMid = Color(0xFF3D52C6);

  /// `total_score >= 0.80`
  static const scoreHigh = Color(0xFF1E8A4F);

  // Semantic
  static const error = Color(0xFFB3261E);
  static const onError = Color(0xFFFFFFFF);
}
