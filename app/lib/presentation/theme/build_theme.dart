import 'package:flutter/material.dart';

import 'package:jobify_app/presentation/theme/jobify_colors.dart';
import 'package:jobify_app/presentation/theme/jobify_radii.dart';
import 'package:jobify_app/presentation/theme/jobify_typography.dart';

/// Single ThemeData factory for both brightness modes.
/// Warm-paper token set — light and dark variants picked by the isDark flag.
ThemeData buildTheme(Brightness brightness) {
  final isDark = brightness == Brightness.dark;

  // ── Pick light / dark token values ───────────────────────────────────────
  final paper = isDark ? JobifyColors.paperDark : JobifyColors.paperLight;
  final panel = isDark ? JobifyColors.panelDark : JobifyColors.panelLight;
  final ink = isDark ? JobifyColors.inkDark : JobifyColors.inkLight;
  final inkSoft = isDark ? JobifyColors.inkSoftDark : JobifyColors.inkSoftLight;
  final line = isDark ? JobifyColors.lineDark : JobifyColors.lineLight;
  final lineStrong =
      isDark ? JobifyColors.lineStrongDark : JobifyColors.lineStrongLight;

  final accent = isDark ? JobifyColors.accentDark : JobifyColors.accentLight;
  final accentDeep =
      isDark ? JobifyColors.accentDeepDark : JobifyColors.accentDeepLight;
  final accentWash =
      isDark ? JobifyColors.accentWashDark : JobifyColors.accentWashLight;
  final accentInk =
      isDark ? JobifyColors.accentInkDark : JobifyColors.accentInkLight;
  final onPrimaryContainer = isDark ? accent : accentDeep;

  final brandBlue =
      isDark ? JobifyColors.brandBlueDark : JobifyColors.brandBlueLight;
  final brandBlueDeep =
      isDark ? JobifyColors.brandBlueDeepDark : JobifyColors.brandBlueDeepLight;
  final brandBlueTint =
      isDark ? JobifyColors.brandBlueTintDark : JobifyColors.brandBlueTintLight;
  const onSecondaryLight = Color(0xFFFFFFFF);
  const onSecondaryDark = Color(0xFF0A1020);
  final onSecondary = isDark ? onSecondaryDark : onSecondaryLight;
  final onSecondaryContainer = isDark ? brandBlue : brandBlueDeep;

  final forest = isDark ? JobifyColors.forestDark : JobifyColors.forestLight;
  final forestSoft =
      isDark ? JobifyColors.forestSoftDark : JobifyColors.forestSoftLight;
  const onTertiaryLight = Color(0xFFFFFFFF);
  const onTertiaryDark = Color(0xFF06210F);
  final onTertiary = isDark ? onTertiaryDark : onTertiaryLight;

  final danger = isDark ? JobifyColors.dangerDark : JobifyColors.dangerLight;
  const onErrorLight = Color(0xFFFFFFFF);
  const onErrorDark = Color(0xFF2A0A06);
  final onError = isDark ? onErrorDark : onErrorLight;

  // ── ColorScheme ──────────────────────────────────────────────────────────
  final scheme = ColorScheme(
    brightness: brightness,
    primary: accent,
    onPrimary: accentInk,
    primaryContainer: accentWash,
    onPrimaryContainer: onPrimaryContainer,
    secondary: brandBlue,
    onSecondary: onSecondary,
    secondaryContainer: brandBlueTint,
    onSecondaryContainer: onSecondaryContainer,
    tertiary: forest,
    onTertiary: onTertiary,
    tertiaryContainer: forestSoft,
    onTertiaryContainer: forest,
    error: danger,
    onError: onError,
    surface: paper,
    onSurface: ink,
    surfaceContainerHighest: panel,
    onSurfaceVariant: inkSoft,
    outline: lineStrong,
    outlineVariant: line,
  );

  final textTheme = JobifyTypography.textTheme(brightness);

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    textTheme: textTheme,
    scaffoldBackgroundColor: scheme.surface,
    appBarTheme: AppBarTheme(
      backgroundColor: scheme.surface,
      foregroundColor: scheme.onSurface,
      centerTitle: false,
      elevation: 0,
      titleTextStyle: textTheme.titleLarge,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        shape: const RoundedRectangleBorder(
          borderRadius: JobifyRadii.borderRadiusMd,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        textStyle: textTheme.labelLarge,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        shape: const RoundedRectangleBorder(
          borderRadius: JobifyRadii.borderRadiusMd,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        textStyle: textTheme.labelLarge,
      ),
    ),
    cardTheme: CardThemeData(
      shape: const RoundedRectangleBorder(
        borderRadius: JobifyRadii.borderRadiusLg,
      ),
      margin: EdgeInsets.zero,
      elevation: 0,
      color: scheme.surfaceContainerHighest,
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      shape: const RoundedRectangleBorder(
        borderRadius: JobifyRadii.borderRadiusMd,
      ),
      backgroundColor: scheme.onSurface,
      contentTextStyle: textTheme.bodyMedium?.copyWith(color: scheme.surface),
    ),
  );
}
