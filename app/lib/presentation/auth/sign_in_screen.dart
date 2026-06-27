import 'dart:math' as math;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show SystemUiOverlayStyle;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:jobify_app/core/error/exceptions.dart';
import 'package:jobify_app/data/auth/google_web_sign_in.dart';
import 'package:jobify_app/presentation/auth/delete_success_snackbar_provider.dart';
import 'package:jobify_app/presentation/auth/sign_in_controller.dart';
import 'package:jobify_app/presentation/theme/jobify_colors.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
import 'package:jobify_app/presentation/theme/jobify_typography.dart';
import 'package:jobify_app/presentation/widgets/arrive.dart';

/// Deep-blue confidence: a full-bleed brand-blue canvas whose hero is a living
/// scene — a person with roles flowing toward them, the brand promise ("Job
/// will find you") made literal — beside the sign-in.
class SignInScreen extends ConsumerWidget {
  const SignInScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // One-time snackbar after account deletion.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (ref.read(deleteSuccessSnackbarProvider)) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Your account has been deleted.')),
        );
        ref.read(deleteSuccessSnackbarProvider.notifier).consume();
      }
    });

    ref.listen<AsyncValue<void>>(signInControllerProvider, (_, next) {
      next.whenOrNull(
        error: (e, _) {
          final msg = switch (e) {
            AuthException(:final slug)
                when slug == 'google_sign_in_cancelled' =>
              null,
            NetworkException _ =>
              "Couldn't reach Jobify. Check your connection.",
            AuthException(:final detail) =>
              detail ?? 'Sign-in failed. Try again.',
            _ => 'Sign-in failed. Try again.',
          };
          if (msg != null) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(msg)),
            );
          }
        },
      );
    });

    final isLoading = ref.watch(signInControllerProvider).isLoading;

    // The gradient sits behind the status bar; request LIGHT status-bar icons
    // so the system clock / battery stay legible (no AppBar to do it for us).
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        body: DecoratedBox(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                JobifyColors.brandCanvasTop,
                JobifyColors.brandCanvasMid,
                JobifyColors.brandCanvasBottom,
              ],
              stops: [0.0, 0.55, 1.0],
            ),
          ),
          child: SafeArea(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final wide = constraints.maxWidth >= 820;
                final sceneSize = wide
                    ? 420.0
                    : (constraints.maxWidth - 48).clamp(0, 340).toDouble();
                final intro = _Intro(isLoading: isLoading, wide: wide);
                final scene =
                    Arrive(index: 1, child: _ArrivalScene(size: sceneSize));
                return Center(
                  child: SingleChildScrollView(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 1080),
                      child: Padding(
                        padding: EdgeInsets.symmetric(
                          horizontal: wide ? 56 : JobifySpacing.xl,
                          vertical: wide ? 48 : JobifySpacing.xxl,
                        ),
                        child: wide
                            ? Row(
                                children: [
                                  Expanded(flex: 5, child: intro),
                                  const SizedBox(width: 40),
                                  Expanded(
                                    flex: 4,
                                    child: Center(child: scene),
                                  ),
                                ],
                              )
                            : Column(
                                mainAxisSize: MainAxisSize.min,
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Center(child: scene),
                                  const SizedBox(height: 36),
                                  intro,
                                ],
                              ),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ),
      ),
    );
  }
}

/// Left/top column: wordmark, the "Job will find you" promise, and sign-in.
class _Intro extends StatelessWidget {
  const _Intro({required this.isLoading, required this.wide});

  final bool isLoading;
  final bool wide;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        const Arrive(index: 0, child: _Wordmark()),
        SizedBox(height: wide ? 40 : 28),
        Arrive(
          index: 1,
          child: Text(
            'Job will\nfind you.',
            style: text.displayLarge?.copyWith(
              fontSize: wide ? 56 : 40,
              height: 1.05,
              letterSpacing: -1,
              fontWeight: FontWeight.w600,
              color: Colors.white,
            ),
          ),
        ),
        const SizedBox(height: JobifySpacing.md),
        Arrive(
          index: 2,
          child: Text(
            'We read your résumé and bring the roles that fit — '
            'with the reason, and the catch, in plain words.',
            style: text.bodyLarge?.copyWith(
              color: Colors.white.withValues(alpha: 0.74),
              height: 1.5,
            ),
          ),
        ),
        SizedBox(height: wide ? 36 : 28),
        Arrive(index: 3, child: _SignInBlock(isLoading: isLoading)),
      ],
    );
  }
}

class _Wordmark extends StatelessWidget {
  const _Wordmark();

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          'Jobify',
          style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                color: Colors.white,
                fontWeight: FontWeight.w600,
                letterSpacing: -0.5,
              ),
        ),
        const SizedBox(width: 8),
        Container(
          width: 7,
          height: 7,
          margin: const EdgeInsets.only(top: 4),
          decoration: const BoxDecoration(
            color: JobifyColors.brandGlow,
            shape: BoxShape.circle,
          ),
        ),
      ],
    );
  }
}

/// The hero animation: a person at the centre with role "chips" continuously
/// drifting inward and being absorbed — "Job will find you." Honors reduced
/// motion live (chips sit static around the person), and pauses while the app
/// is backgrounded.
class _ArrivalScene extends StatefulWidget {
  const _ArrivalScene({required this.size});

  final double size;

  @override
  State<_ArrivalScene> createState() => _ArrivalSceneState();
}

class _ArrivalSceneState extends State<_ArrivalScene>
    with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 11),
  );

  static const _labels = <String>[
    'Backend Engineer',
    'Product Designer',
    'Data Engineer',
    '₹18–28L',
    'Remote-first',
    '92% match',
  ];

  // Scene geometry / animation thresholds (fractions of `size`).
  static const _kPersonRatio = 0.135;
  static const _kOrbitStart = 0.47;
  static const _kOrbitEndGap = 0.05;
  static const _kFadeIn = 0.12;
  static const _kFadeOut = 0.8;
  static const _kReducedFrame = 0.42; // static frame shown under reduced motion

  // Built once per size: chip widgets (labels invariant), per-chip unit
  // vectors, and the person avatar — so the per-frame builder only re-wraps
  // them in fresh Transform/Opacity rather than rebuilding their subtrees.
  double _builtForSize = -1;
  late List<Widget> _chips;
  late List<double> _cos;
  late List<double> _sin;
  late Widget _avatar;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _reconcileMotion(); // reacts to live reduced-motion (MediaQuery) changes
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _reconcileMotion();
    } else if (_c.isAnimating) {
      _c.stop(); // don't composite at 60fps while backgrounded
    }
  }

  void _reconcileMotion() {
    final reduced = MediaQuery.of(context).disableAnimations;
    if (reduced) {
      if (_c.isAnimating) _c.stop();
    } else if (!_c.isAnimating) {
      _c.repeat();
    }
  }

  void _ensureCache(double s) {
    if (_builtForSize == s) return;
    _builtForSize = s;
    final n = _labels.length;
    _chips = [for (final l in _labels) _JobChip(label: l)];
    _cos = List<double>.filled(n, 0);
    _sin = List<double>.filled(n, 0);
    for (var i = 0; i < n; i++) {
      final phase = i / n;
      final angle =
          2 * math.pi * phase - math.pi / 2 + 0.5 * math.sin(phase * 6.3);
      _cos[i] = math.cos(angle);
      _sin[i] = math.sin(angle);
    }
    // RepaintBoundary so the avatar's blur shadow isn't re-rastered each frame.
    _avatar = RepaintBoundary(child: _PersonAvatar(radius: s * _kPersonRatio));
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.size;
    _ensureCache(s);
    final reduced = MediaQuery.of(context).disableAnimations;
    final rPerson = s * _kPersonRatio;
    final rStart = s * _kOrbitStart;
    final rEnd = rPerson + s * _kOrbitEndGap;
    final n = _labels.length;

    return SizedBox(
      width: s,
      height: s,
      child: AnimatedBuilder(
        animation: _c,
        // Avatar built once and handed in as `child` — not rebuilt per frame.
        child: Center(child: _avatar),
        builder: (context, avatar) {
          final t = reduced ? _kReducedFrame : _c.value;
          final children = <Widget>[];

          // Attract ring pulsing out from the person.
          final ringSize = rPerson * 2 * (0.9 + t * 1.7);
          children.add(
            Center(
              child: Opacity(
                opacity: (1 - t) * 0.45,
                child: Container(
                  width: ringSize,
                  height: ringSize,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: Colors.white.withValues(alpha: 0.4),
                    ),
                  ),
                ),
              ),
            ),
          );

          // Cached role chips flowing inward toward the person.
          for (var i = 0; i < n; i++) {
            final p = (t + i / n) % 1.0;
            final radius =
                rStart + (rEnd - rStart) * Curves.easeIn.transform(p);
            final op = reduced
                ? 0.9
                : (p < _kFadeIn
                    ? p / _kFadeIn
                    : (p > _kFadeOut ? (1 - p) / (1 - _kFadeOut) : 1.0));
            children.add(
              Center(
                child: Transform.translate(
                  offset: Offset(_cos[i] * radius, _sin[i] * radius),
                  child: Opacity(
                    opacity: op.clamp(0.0, 1.0),
                    child: _chips[i],
                  ),
                ),
              ),
            );
          }

          children.add(avatar!); // person on top — roles arrive at them
          return Stack(alignment: Alignment.center, children: children);
        },
      ),
    );
  }
}

class _JobChip extends StatelessWidget {
  const _JobChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.12),
        border: Border.all(color: Colors.white.withValues(alpha: 0.22)),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: JobifyTypography.mono(
          fontSize: 11.5,
          color: Colors.white.withValues(alpha: 0.92),
        ),
      ),
    );
  }
}

class _PersonAvatar extends StatelessWidget {
  const _PersonAvatar({required this.radius});

  final double radius;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: radius * 2,
      height: radius * 2,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: Colors.white.withValues(alpha: 0.16),
        border: Border.all(
          color: Colors.white.withValues(alpha: 0.55),
          width: 1.5,
        ),
        boxShadow: [
          BoxShadow(
            color: JobifyColors.brandGlow.withValues(alpha: 0.35),
            blurRadius: 28,
            spreadRadius: 2,
          ),
        ],
      ),
      child: Icon(Icons.person, color: Colors.white, size: radius * 1.25),
    );
  }
}

/// The sign-in affordance (web rendered button / mobile imperative button),
/// styled to pop on the deep-blue canvas.
class _SignInBlock extends ConsumerWidget {
  const _SignInBlock({required this.isLoading});

  final bool isLoading;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (kIsWeb) {
      return _WebSignInButton(isLoading: isLoading);
    }
    return FilledButton.icon(
      style: FilledButton.styleFrom(
        backgroundColor: Colors.white,
        foregroundColor: JobifyColors.brandCanvasMid,
        disabledBackgroundColor: Colors.white.withValues(alpha: 0.7),
        padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 16),
      ),
      icon: isLoading
          ? const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: JobifyColors.brandCanvasMid,
              ),
            )
          : const Icon(Icons.login),
      label: Text(isLoading ? 'Signing in…' : 'Continue with Google'),
      onPressed: isLoading
          ? null
          : () =>
              ref.read(signInControllerProvider.notifier).signInWithGoogle(),
    );
  }
}

/// Web sign-in affordance: shows Google's rendered button once the GIS client
/// is initialized, a (light) spinner while initializing or while the backend
/// exchange is in flight, and a fallback message if init failed.
class _WebSignInButton extends ConsumerWidget {
  const _WebSignInButton({required this.isLoading});

  final bool isLoading;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (isLoading) {
      return const _LightSpinner();
    }
    return ref.watch(googleWebSignInProvider).when(
          data: (google) => Align(
            alignment: Alignment.centerLeft,
            child: google.button(),
          ),
          loading: () => const _LightSpinner(),
          error: (_, __) => Text(
            "Couldn't load Google sign-in. Refresh and try again.",
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.white.withValues(alpha: 0.8),
                ),
          ),
        );
  }
}

class _LightSpinner extends StatelessWidget {
  const _LightSpinner();

  @override
  Widget build(BuildContext context) => const SizedBox(
        width: 24,
        height: 24,
        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
      );
}
