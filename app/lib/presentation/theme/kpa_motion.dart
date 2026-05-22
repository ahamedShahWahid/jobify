import 'package:flutter/material.dart';

/// Motion tokens — v0 just re-exports Material defaults. The indirection
/// means we can adjust globally later without sweeping every call site.
abstract final class KpaMotion {
  static const Duration durationShort  = Durations.short3;    // 150ms
  static const Duration durationMedium = Durations.medium2;   // 250ms
  static const Duration durationLong   = Durations.long2;     // 500ms

  static const Curve curveStandard   = Easing.standard;
  static const Curve curveEmphasized = Easing.emphasizedAccelerate;
}
