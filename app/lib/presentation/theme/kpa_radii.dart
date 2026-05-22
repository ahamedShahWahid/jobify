import 'package:flutter/widgets.dart';

abstract final class KpaRadii {
  static const double sm   = 4;
  static const double md   = 8;
  static const double lg   = 12;
  static const double xl   = 16;
  static const double pill = 999;

  static const radiusSm   = Radius.circular(sm);
  static const radiusMd   = Radius.circular(md);
  static const radiusLg   = Radius.circular(lg);
  static const radiusXl   = Radius.circular(xl);
  static const radiusPill = Radius.circular(pill);

  static const borderRadiusSm   = BorderRadius.all(radiusSm);
  static const borderRadiusMd   = BorderRadius.all(radiusMd);
  static const borderRadiusLg   = BorderRadius.all(radiusLg);
  static const borderRadiusXl   = BorderRadius.all(radiusXl);
  static const borderRadiusPill = BorderRadius.all(radiusPill);
}
