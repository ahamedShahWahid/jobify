import 'package:flutter/material.dart';

import 'package:jobify_app/presentation/theme/jobify_colors.dart';
import 'package:jobify_app/presentation/theme/jobify_radii.dart';
import 'package:jobify_app/presentation/theme/jobify_typography.dart';

/// Single ThemeData factory for both brightness modes.
/// Clear Sky token set — light and dark variants picked by the isDark flag.
ThemeData buildTheme(Brightness brightness) {
  final isDark = brightness == Brightness.dark;

  final paper = isDark ? JobifyColors.paperDark : JobifyColors.paperLight;
  final panel = isDark ? JobifyColors.panelDark : JobifyColors.panelLight;
  final ink = isDark ? JobifyColors.inkDark : JobifyColors.inkLight;
  final inkSoft = isDark ? JobifyColors.inkSoftDark : JobifyColors.inkSoftLight;
  final line = isDark ? JobifyColors.lineDark : JobifyColors.lineLight;
  final lineStrong =
      isDark ? JobifyColors.lineStrongDark : JobifyColors.lineStrongLight;

  final brand =
      isDark ? JobifyColors.brandBlueDark : JobifyColors.brandBlueLight;
  final brandDeep =
      isDark ? JobifyColors.brandBlueDeepDark : JobifyColors.brandBlueDeepLight;
  final brandTint =
      isDark ? JobifyColors.brandBlueTintDark : JobifyColors.brandBlueTintLight;
  final brandInk =
      isDark ? JobifyColors.brandInkDark : JobifyColors.brandInkLight;

  final danger = isDark ? JobifyColors.dangerDark : JobifyColors.dangerLight;
  final onDanger = isDark ? const Color(0xFF2A0606) : const Color(0xFFFFFFFF);

  final scheme = ColorScheme(
    brightness: brightness,
    // Brand blue is primary: CTAs, the "Applied" pill, selected nav.
    primary: brand,
    onPrimary: brandInk,
    primaryContainer: brandTint,
    onPrimaryContainer: brand,
    // secondary / tertiary are not consumed by any screen; keep them in the
    // brand family so nothing renders an off-palette color if used later.
    secondary: brandDeep,
    onSecondary: brandInk,
    secondaryContainer: brandTint,
    onSecondaryContainer: brand,
    tertiary: brandDeep,
    onTertiary: brandInk,
    tertiaryContainer: brandTint,
    onTertiaryContainer: brand,
    error: danger,
    onError: onDanger,
    errorContainer:
        isDark ? JobifyColors.caveatWashDark : const Color(0xFFF7DCD8),
    onErrorContainer: danger,
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
        borderRadius: JobifyRadii.borderRadiusXl,
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
