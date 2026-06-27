import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show SystemUiOverlayStyle;

import 'package:jobify_app/presentation/theme/jobify_colors.dart';

/// Deep-blue hero header — the "Deep Blue Confidence" identity carried across
/// every main screen. A full-width brand-blue gradient band with a large white
/// title, an optional subtitle, and an optional trailing action.
///
/// Sits at the top of a screen's body (the Scaffold drops its AppBar); it
/// renders its own top SafeArea so it tucks under the status bar, and an
/// [AnnotatedRegion] requesting LIGHT status-bar icons so the system clock /
/// battery stay legible on the dark gradient (the dropped AppBar used to do
/// this automatically). [trailing] is rendered with white icon AND white
/// button-label colours so any `Icon`, `IconButton`, or `TextButton` reads on
/// the blue without the caller setting a foreground colour.
class BoldHeader extends StatelessWidget {
  const BoldHeader({
    required this.title,
    this.subtitle,
    this.trailing,
    super.key,
  });

  final String title;
  final String? subtitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Container(
        width: double.infinity,
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [JobifyColors.brandCanvasTop, JobifyColors.brandCanvasMid],
          ),
        ),
        child: SafeArea(
          bottom: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 12, 22),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        title,
                        style: text.headlineLarge?.copyWith(
                          color: Colors.white,
                          fontWeight: FontWeight.w600,
                          letterSpacing: -0.5,
                        ),
                      ),
                      if (subtitle != null) ...[
                        const SizedBox(height: 4),
                        Text(
                          subtitle!,
                          style: text.bodyMedium?.copyWith(
                            color: Colors.white.withValues(alpha: 0.72),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                if (trailing != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: _OnCanvas(child: trailing!),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Forces white foregrounds for whatever sits on the brand canvas — covers
/// plain `Text`, `Icon`/`IconButton`, and `TextButton` labels alike, so a
/// caller never has to remember to set `foregroundColor: Colors.white`.
class _OnCanvas extends StatelessWidget {
  const _OnCanvas({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return IconTheme.merge(
      data: const IconThemeData(color: Colors.white),
      child: TextButtonTheme(
        data: TextButtonThemeData(
          style: TextButton.styleFrom(foregroundColor: Colors.white),
        ),
        child: DefaultTextStyle.merge(
          style: const TextStyle(color: Colors.white),
          child: child,
        ),
      ),
    );
  }
}

/// A [Scaffold] whose body is a [BoldHeader] above a flex-filling [child] —
/// the shared shape every main tab screen uses (feed, saved, applications,
/// profile), so the wrapper lives in one place instead of four.
class BoldScaffold extends StatelessWidget {
  const BoldScaffold({required this.header, required this.child, super.key});

  final BoldHeader header;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          header,
          Expanded(child: child),
        ],
      ),
    );
  }
}
