import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Jobify "Clear Sky" typography.
///
/// Display = Schibsted Grotesk w600 (calm, not heavy-black). Body/labels =
/// Inter. Data (score stamp, ₹, dates) = IBM Plex Mono via [mono]. All via
/// google_fonts — tests must use ThemeData.light(), never buildTheme().
abstract final class JobifyTypography {
  static TextTheme textTheme(Brightness brightness) {
    final base = brightness == Brightness.dark
        ? Typography.whiteMountainView
        : Typography.blackMountainView;
    return GoogleFonts.interTextTheme(base).copyWith(
      displayLarge: GoogleFonts.schibstedGrotesk(
        fontSize: 34,
        fontWeight: FontWeight.w600,
        height: 1.15,
      ),
      displayMedium: GoogleFonts.schibstedGrotesk(
        fontSize: 28,
        fontWeight: FontWeight.w600,
        height: 1.18,
      ),
      headlineLarge: GoogleFonts.schibstedGrotesk(
        fontSize: 24,
        fontWeight: FontWeight.w600,
        height: 1.22,
      ),
      headlineMedium: GoogleFonts.schibstedGrotesk(
        fontSize: 20,
        fontWeight: FontWeight.w600,
        height: 1.28,
      ),
      titleLarge: GoogleFonts.inter(
        fontSize: 18,
        fontWeight: FontWeight.w600,
        height: 1.35,
      ),
      titleMedium: GoogleFonts.inter(
        fontSize: 16,
        fontWeight: FontWeight.w600,
        height: 1.40,
      ),
      bodyLarge: GoogleFonts.inter(
        fontSize: 16,
        fontWeight: FontWeight.w400,
        height: 1.50,
      ),
      bodyMedium: GoogleFonts.inter(
        fontSize: 14,
        fontWeight: FontWeight.w400,
        height: 1.50,
      ),
      bodySmall: GoogleFonts.inter(
        fontSize: 12,
        fontWeight: FontWeight.w400,
        height: 1.40,
      ),
      labelLarge: GoogleFonts.inter(
        fontSize: 14,
        fontWeight: FontWeight.w600,
        height: 1.20,
      ),
      labelMedium: GoogleFonts.inter(
        fontSize: 12,
        fontWeight: FontWeight.w600,
        height: 1.20,
      ),
      labelSmall: GoogleFonts.inter(
        fontSize: 11,
        fontWeight: FontWeight.w600,
        height: 1.20,
      ),
    );
  }

  /// The data / "shows its work" voice — IBM Plex Mono. Used for the score
  /// stamp, ₹ figures, timestamps. Pass the resolved color from the caller.
  static TextStyle mono({
    required double fontSize,
    FontWeight fontWeight = FontWeight.w500,
    Color? color,
    double? letterSpacing,
  }) =>
      GoogleFonts.ibmPlexMono(
        fontSize: fontSize,
        fontWeight: fontWeight,
        color: color,
        letterSpacing: letterSpacing,
      );
}
