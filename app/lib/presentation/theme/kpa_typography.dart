import 'package:flutter/material.dart';

/// KPA typography — Inter via google_fonts, six size roles mapped onto
/// Material 3's text theme. The roles match Material 3 naming so widgets
/// can refer to `Theme.of(context).textTheme.headlineMedium` directly.
///
/// Note: google_fonts is loaded lazily in build_theme when needed at runtime.
abstract final class KpaTypography {
  static TextTheme _buildBaseTextTheme(Brightness brightness) {
    final base = brightness == Brightness.dark
        ? Typography.whiteMountainView
        : Typography.blackMountainView;
    return base.copyWith(
      displayLarge: _textStyle(
        fontSize: 36,
        fontWeight: FontWeight.w700,
        height: 1.15,
      ),
      displayMedium: _textStyle(
        fontSize: 28,
        fontWeight: FontWeight.w700,
        height: 1.20,
      ),
      headlineLarge: _textStyle(
        fontSize: 24,
        fontWeight: FontWeight.w600,
        height: 1.25,
      ),
      headlineMedium: _textStyle(
        fontSize: 20,
        fontWeight: FontWeight.w600,
        height: 1.30,
      ),
      titleLarge: _textStyle(
        fontSize: 18,
        fontWeight: FontWeight.w600,
        height: 1.35,
      ),
      titleMedium: _textStyle(
        fontSize: 16,
        fontWeight: FontWeight.w600,
        height: 1.40,
      ),
      bodyLarge: _textStyle(
        fontSize: 16,
        fontWeight: FontWeight.w400,
        height: 1.45,
      ),
      bodyMedium: _textStyle(
        fontSize: 14,
        fontWeight: FontWeight.w400,
        height: 1.45,
      ),
      bodySmall: _textStyle(
        fontSize: 12,
        fontWeight: FontWeight.w400,
        height: 1.40,
      ),
      labelLarge: _textStyle(
        fontSize: 14,
        fontWeight: FontWeight.w600,
        height: 1.20,
      ),
      labelMedium: _textStyle(
        fontSize: 12,
        fontWeight: FontWeight.w600,
        height: 1.20,
      ),
      labelSmall: _textStyle(
        fontSize: 11,
        fontWeight: FontWeight.w600,
        height: 1.20,
      ),
    );
  }

  static TextStyle _textStyle({
    required double fontSize,
    required FontWeight fontWeight,
    required double height,
  }) {
    return TextStyle(
      fontSize: fontSize,
      fontWeight: fontWeight,
      height: height,
      fontFamily: 'Inter',
    );
  }

  static TextTheme textTheme(Brightness brightness) {
    return _buildBaseTextTheme(brightness);
  }
}
