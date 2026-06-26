# Clear Sky — Flutter Reskin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reskin the Jobify Flutter app with the "Clear Sky" visual direction — a calm, blue-anchored identity where the match *sentence* is the hero, the score is a demoted mono stamp, color is rationed (brand blue = the match, amber = the honest caveat), with one orchestrated "the role arrives" motion moment.

**Architecture:** A pure visual-layer change. Replace the global token values (`jobify_colors.dart`) and remap the `ColorScheme` in `build_theme.dart` so every screen — which already consumes `Theme.of(context).colorScheme.*` / `textTheme.*` — inherits the new look. Swap typeface families. Rework two raw-token consumers (`jobify_score_badge.dart`, `feed_item_card.dart`) and add one reusable entrance-motion widget. No routing/data/behavior changes.

**Tech Stack:** Flutter, Material 3, `google_fonts` (Schibsted Grotesk / Inter / IBM Plex Mono), Riverpod (unchanged).

## Global Constraints

- **Both palettes.** Every token defines a `*Light` and `*Dark` value; dark mode is live (profile switcher). Verify both themes before completion.
- **Rationed color.** Only two hues carry meaning: brand blue `#0048A8` (light) / `#5B9BFF` (dark) = the match + primary action; amber `#C77A1E` / `#E0A24A` = the honest caveat, only. Everything else is ink on cool sky.
- **No hardcoded near-white/near-dark foregrounds** inside any brand- or caveat-filled panel — resolve from tokens (dark-mode auto-invert trap).
- **Widget tests use `ThemeData.light(useMaterial3: true)`, NOT `buildTheme()`** (`buildTheme` → `google_fonts` network fetch fails offline/CI). Existing invariant — do not change it.
- **One animation only** — the arrival stagger (feed first-load/refresh) + its sign-in sibling. Respect reduced motion (`MediaQuery.disableAnimations`).
- **CI verbatim (from `app/`):** `dart format --set-exit-if-changed lib test` · `flutter analyze` · `flutter test`. All green before a task is done.
- Run all `flutter`/`dart` commands from `app/` (`cd /Users/ahamadshah/ahamed_personal/jobify/app`).

---

## File Structure

**Modify:**
- `lib/presentation/theme/jobify_colors.dart` — replace token set (Task 1)
- `lib/presentation/theme/build_theme.dart` — remap `ColorScheme` (Task 1)
- `lib/presentation/theme/jobify_typography.dart` — Schibsted/Inter/IBM Plex Mono + scale (Task 2)
- `lib/presentation/theme/jobify_motion.dart` — add spring curve (Task 4)
- `lib/presentation/widgets/jobify_score_badge.dart` — mono two-state stamp (Task 3)
- `lib/presentation/feed/feed_item_card.dart` — invert hierarchy (Task 5)
- `lib/presentation/feed/feed_screen.dart` — wrap list in arrival (Task 5)
- `lib/presentation/auth/sign_in_screen.dart` — restyle + entrance (Task 6)
- `lib/presentation/job_detail/job_detail_screen.dart` — match-card hierarchy (Task 7)
- `lib/presentation/applications/applications_screen.dart` — status pills (Task 7)
- `lib/presentation/profile/profile_screen.dart` — mono data, section headers (Task 7)
- `lib/presentation/widgets/jobify_shell_scaffold.dart` + recruiter shell — nav styling (Task 7)
- shared widgets (`jobify_empty_state.dart`, `jobify_loading_view.dart`, `jobify_error_view.dart`) — token sanity (Task 7)

**Create:**
- `lib/presentation/widgets/arrive.dart` — reusable entrance-motion widget (Task 4)
- `test/unit/presentation/theme/jobify_colors_test.dart` (Task 1)
- `test/widget/widgets/arrive_test.dart` (Task 4)

**Update existing tests:**
- `test/widget/widgets/primitive_widgets_test.dart` — score-badge band/percent assertions (Task 3)
- `test/widget/job_applicants_screen_test.dart` — `find.text('82%')` (Task 3, keep `%`)

---

## Task 1: Token foundation — Clear Sky palette + ColorScheme remap

**Files:**
- Modify: `lib/presentation/theme/jobify_colors.dart` (full replace)
- Modify: `lib/presentation/theme/build_theme.dart:8-95` (ColorScheme block)
- Test: `test/unit/presentation/theme/jobify_colors_test.dart` (create)

**Interfaces:**
- Produces: `JobifyColors` with tokens `paper/paper2/paper3/panel`, `ink/inkSoft/inkFaint`, `line/lineStrong`, `brandBlue/brandBlueDeep/brandBlueTint/brandInk`, `caveat/caveatWash/caveatInk`, `danger` — each as `*Light` / `*Dark` `Color` constants. (Removes `accent*`, `forest*`, `gold*`, `score*`.)
- Produces: `buildTheme(Brightness)` where `colorScheme.primary` = brand blue, `primaryContainer` = `brandBlueTint`, `onPrimaryContainer` = brand blue, `error` = danger.

- [ ] **Step 1: Write the failing test**

Create `test/unit/presentation/theme/jobify_colors_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/presentation/theme/jobify_colors.dart';

void main() {
  test('brand blue is the one meaning color', () {
    expect(JobifyColors.brandBlueLight, const Color(0xFF0048A8));
    expect(JobifyColors.brandBlueDark, const Color(0xFF5B9BFF));
  });

  test('caveat amber is defined for both themes', () {
    expect(JobifyColors.caveatLight, const Color(0xFFC77A1E));
    expect(JobifyColors.caveatDark, const Color(0xFFE0A24A));
  });

  test('surface is cool sky / calm night (not warm, not black)', () {
    expect(JobifyColors.paperLight, const Color(0xFFF4F6F9));
    expect(JobifyColors.paperDark, const Color(0xFF0B1620));
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && flutter test test/unit/presentation/theme/jobify_colors_test.dart`
Expected: FAIL — `caveatLight` / new values not defined (or old paper value mismatch).

- [ ] **Step 3: Replace `jobify_colors.dart`**

```dart
import 'package:flutter/material.dart';

/// Jobify "Clear Sky" color tokens — light and dark variants.
///
/// Color is rationed: only `brandBlue*` (the match / primary action) and
/// `caveat*` (the honest weakness) carry meaning. Everything else is ink on a
/// cool sky surface. `buildTheme` picks the light/dark pair via its isDark flag.
abstract final class JobifyColors {
  // ── Sky surfaces ────────────────────────────────────────────────────────
  static const paperLight = Color(0xFFF4F6F9);
  static const paperDark = Color(0xFF0B1620);

  static const paper2Light = Color(0xFFEAEEF4);
  static const paper2Dark = Color(0xFF0F1C28);

  static const paper3Light = Color(0xFFDFE5EE);
  static const paper3Dark = Color(0xFF0A141D);

  static const panelLight = Color(0xFFFFFFFF);
  static const panelDark = Color(0xFF13212E);

  // ── Ink (text / icon) ───────────────────────────────────────────────────
  static const inkLight = Color(0xFF0F2440);
  static const inkDark = Color(0xFFE8EDF3);

  static const inkSoftLight = Color(0xFF5C6B7E);
  static const inkSoftDark = Color(0xFF9DB0C2);

  static const inkFaintLight = Color(0xFF94A1B2);
  static const inkFaintDark = Color(0xFF5E7186);

  // ── Lines / dividers ────────────────────────────────────────────────────
  static const lineLight = Color(0xFFE3E8EF);
  static const lineDark = Color(0xFF1E2D3B);

  static const lineStrongLight = Color(0xFFCED7E2);
  static const lineStrongDark = Color(0xFF2C3F50);

  // ── Brand blue — the one meaning color (the match + primary action) ──────
  static const brandBlueLight = Color(0xFF0048A8);
  static const brandBlueDark = Color(0xFF5B9BFF);

  static const brandBlueDeepLight = Color(0xFF00367D);
  static const brandBlueDeepDark = Color(0xFF3F86F5);

  static const brandBlueTintLight = Color(0xFFE7EEF8); // wash behind a match
  static const brandBlueTintDark = Color(0xFF13294A);

  static const brandInkLight = Color(0xFFFFFFFF); // text/icon on brand fill
  static const brandInkDark = Color(0xFF04101F);

  // ── Caveat amber — the honest weakness, only ────────────────────────────
  static const caveatLight = Color(0xFFC77A1E);
  static const caveatDark = Color(0xFFE0A24A);

  static const caveatWashLight = Color(0xFFFBF0E0);
  static const caveatWashDark = Color(0xFF2A1F0E);

  static const caveatInkLight = Color(0xFFFFFFFF);
  static const caveatInkDark = Color(0xFF1F1404);

  // ── Danger / error ──────────────────────────────────────────────────────
  static const dangerLight = Color(0xFFC0362B);
  static const dangerDark = Color(0xFFFF6A5A);
}
```

- [ ] **Step 4: Remap the `ColorScheme` in `build_theme.dart`**

Replace the token-pick block and `ColorScheme` (lines ~12–82) with this. Leave the `ThemeData(...)` body below it unchanged **except** bump the card shape to `xl` (see Step 5):

```dart
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
    errorContainer: isDark
        ? JobifyColors.caveatWashDark
        : const Color(0xFFF7DCD8),
    onErrorContainer: danger,
    surface: paper,
    onSurface: ink,
    surfaceContainerHighest: panel,
    onSurfaceVariant: inkSoft,
    outline: lineStrong,
    outlineVariant: line,
  );
```

- [ ] **Step 5: Soften the card shape (same file, `cardTheme`)**

Change the card shape radius from `borderRadiusLg` to `borderRadiusXl` so cards read as the soft "arrived object":

```dart
    cardTheme: CardThemeData(
      shape: const RoundedRectangleBorder(
        borderRadius: JobifyRadii.borderRadiusXl,
      ),
      margin: EdgeInsets.zero,
      elevation: 0,
      color: scheme.surfaceContainerHighest,
    ),
```

- [ ] **Step 6: Run analyze + the token test**

Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && flutter analyze && flutter test test/unit/presentation/theme/jobify_colors_test.dart`
Expected: analyze PASSES (any stray `accent*`/`forest*`/`gold*`/`score*` reference would be a compile error here — `jobify_score_badge.dart` still references `score*`, so analyze will FAIL on that file). **If analyze fails only inside `jobify_score_badge.dart`, that is expected — Task 3 fixes it.** To unblock this task's commit, apply the temporary shim in Step 7.

- [ ] **Step 7: Temporary score-badge shim (keeps the tree compiling until Task 3)**

In `jobify_score_badge.dart`, replace the three `JobifyColors.score*` references in `_bandColor` with the brand token so the tree compiles now; Task 3 replaces this method entirely:

```dart
  Color _bandColor(bool isDark) =>
      isDark ? JobifyColors.brandBlueDark : JobifyColors.brandBlueLight;
```

…and update its single call site to pass `Theme.of(context).brightness == Brightness.dark`. (Task 3 throws all of this away.)

- [ ] **Step 8: Run analyze + format, then commit**

Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && dart format lib test && flutter analyze && flutter test test/unit/presentation/theme/jobify_colors_test.dart`
Expected: all PASS.

```bash
cd /Users/ahamadshah/ahamed_personal/jobify
git add app/lib/presentation/theme/jobify_colors.dart app/lib/presentation/theme/build_theme.dart app/lib/presentation/widgets/jobify_score_badge.dart app/test/unit/presentation/theme/jobify_colors_test.dart
git commit -m "feat(app): Clear Sky color tokens + ColorScheme remap (brand-blue primary)"
```

---

## Task 2: Typography — Schibsted Grotesk / Inter / IBM Plex Mono

**Files:**
- Modify: `lib/presentation/theme/jobify_typography.dart` (full replace of the role map)

**Interfaces:**
- Produces: `JobifyTypography.textTheme(Brightness)` where display roles use Schibsted Grotesk (w600), titles/body/labels use Inter, and a `static TextStyle mono({...})` helper returns IBM Plex Mono for data (score stamp, ₹, dates).

- [ ] **Step 1: Replace the typography role map**

```dart
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
          fontSize: 34, fontWeight: FontWeight.w600, height: 1.15),
      displayMedium: GoogleFonts.schibstedGrotesk(
          fontSize: 28, fontWeight: FontWeight.w600, height: 1.18),
      headlineLarge: GoogleFonts.schibstedGrotesk(
          fontSize: 24, fontWeight: FontWeight.w600, height: 1.22),
      headlineMedium: GoogleFonts.schibstedGrotesk(
          fontSize: 20, fontWeight: FontWeight.w600, height: 1.28),
      titleLarge: GoogleFonts.inter(
          fontSize: 18, fontWeight: FontWeight.w600, height: 1.35),
      titleMedium: GoogleFonts.inter(
          fontSize: 16, fontWeight: FontWeight.w600, height: 1.40),
      bodyLarge: GoogleFonts.inter(
          fontSize: 16, fontWeight: FontWeight.w400, height: 1.50),
      bodyMedium: GoogleFonts.inter(
          fontSize: 14, fontWeight: FontWeight.w400, height: 1.50),
      bodySmall: GoogleFonts.inter(
          fontSize: 12, fontWeight: FontWeight.w400, height: 1.40),
      labelLarge: GoogleFonts.inter(
          fontSize: 14, fontWeight: FontWeight.w600, height: 1.20),
      labelMedium: GoogleFonts.inter(
          fontSize: 12, fontWeight: FontWeight.w600, height: 1.20),
      labelSmall: GoogleFonts.inter(
          fontSize: 11, fontWeight: FontWeight.w600, height: 1.20),
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
```

- [ ] **Step 2: Verify analyze + format pass**

Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && dart format lib && flutter analyze`
Expected: PASS. (Typography is not unit-tested — `buildTheme`/`google_fonts` can't run in CI; the gate is analyze + the visual sweep in Task 8.)

- [ ] **Step 3: Visual smoke (optional but recommended)**

Run the app and confirm display headings render in Schibsted Grotesk and body in Inter (`flutter run -d macos` or your usual device). Reduced-motion not relevant here.

- [ ] **Step 4: Commit**

```bash
cd /Users/ahamadshah/ahamed_personal/jobify
git add app/lib/presentation/theme/jobify_typography.dart
git commit -m "feat(app): Clear Sky typography — Schibsted Grotesk / Inter / IBM Plex Mono"
```

---

## Task 3: Score badge → demoted mono stamp (two-state)

**Files:**
- Modify: `lib/presentation/widgets/jobify_score_badge.dart` (full replace)
- Test: `test/widget/widgets/primitive_widgets_test.dart` (update the two score-badge tests)

**Interfaces:**
- Consumes: `JobifyColors.brandBlue*`, `inkSoft*`, `JobifyTypography.mono`.
- Produces: `JobifyScoreBadge(score: double)` rendering `"<pct>%"` in IBM Plex Mono — **brand blue when `score >= 0.80`** (strong match), otherwise **inkSoft** (quiet). No filled pill background. Static `bool JobifyScoreBadge.isStrong(double score) => score >= 0.80`.

- [ ] **Step 1: Write the failing test (update `primitive_widgets_test.dart`)**

Replace the two existing `JobifyScoreBadge` tests (around lines 69–80) with:

```dart
  testWidgets('JobifyScoreBadge renders rounded percent in mono', (tester) async {
    await tester.pumpWidget(_wrap(const JobifyScoreBadge(score: 0.857)));
    expect(find.text('86%'), findsOneWidget);
  });

  test('JobifyScoreBadge.isStrong gates on 0.80', () {
    expect(JobifyScoreBadge.isStrong(0.79), isFalse);
    expect(JobifyScoreBadge.isStrong(0.80), isTrue);
    expect(JobifyScoreBadge.isStrong(0.95), isTrue);
  });

  testWidgets('strong match uses brand blue, weak uses inkSoft', (tester) async {
    await tester.pumpWidget(_wrap(const JobifyScoreBadge(score: 0.95)));
    final strong = tester.widget<Text>(find.text('95%'));
    expect(strong.style?.color, JobifyColors.brandBlueLight);

    await tester.pumpWidget(_wrap(const JobifyScoreBadge(score: 0.5)));
    final weak = tester.widget<Text>(find.text('50%'));
    expect(weak.style?.color, JobifyColors.inkSoftLight);
  });
```

Ensure the file imports `package:jobify_app/presentation/theme/jobify_colors.dart`. (`_wrap` wraps in `MaterialApp(theme: ThemeData.light(useMaterial3: true))` — confirm the existing helper does this; it does.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && flutter test test/widget/widgets/primitive_widgets_test.dart`
Expected: FAIL — `isStrong` undefined / color mismatch (still the brand-shim pill from Task 1).

- [ ] **Step 3: Replace `jobify_score_badge.dart`**

```dart
import 'package:flutter/material.dart';

import 'package:jobify_app/presentation/theme/jobify_colors.dart';
import 'package:jobify_app/presentation/theme/jobify_typography.dart';

/// The match score, demoted to a quiet monospace stamp.
///
/// Brand blue when the match is strong (>= 0.80) — "worth your attention" —
/// otherwise inkSoft. No filled pill: the *sentence* is the hero, not the
/// number.
class JobifyScoreBadge extends StatelessWidget {
  const JobifyScoreBadge({required this.score, super.key});

  final double score;

  static bool isStrong(double score) => score >= 0.80;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final percent = (score * 100).round().clamp(0, 100);
    final color = isStrong(score)
        ? (isDark ? JobifyColors.brandBlueDark : JobifyColors.brandBlueLight)
        : (isDark ? JobifyColors.inkSoftDark : JobifyColors.inkSoftLight);
    return Text(
      '$percent%',
      style: JobifyTypography.mono(
        fontSize: 13,
        fontWeight: FontWeight.w600,
        color: color,
        letterSpacing: -0.2,
      ),
    );
  }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && flutter test test/widget/widgets/primitive_widgets_test.dart`
Expected: PASS.

- [ ] **Step 5: Fix the other affected test**

`test/widget/job_applicants_screen_test.dart:37` asserts `find.text('82%')` — still valid (we keep the `%`). Run it to confirm:
Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && flutter test test/widget/job_applicants_screen_test.dart`
Expected: PASS (the stamp still renders `82%`). If it fails on a color/pill assertion, update that assertion to match the mono stamp.

- [ ] **Step 6: Format, analyze, commit**

Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && dart format lib test && flutter analyze`
Expected: PASS.

```bash
cd /Users/ahamadshah/ahamed_personal/jobify
git add app/lib/presentation/widgets/jobify_score_badge.dart app/test/widget/widgets/primitive_widgets_test.dart
git commit -m "feat(app): demote score to a two-state mono stamp"
```

---

## Task 4: "The role arrives" — entrance-motion widget

**Files:**
- Create: `lib/presentation/widgets/arrive.dart`
- Modify: `lib/presentation/theme/jobify_motion.dart` (add spring curve constant)
- Test: `test/widget/widgets/arrive_test.dart` (create)

**Interfaces:**
- Produces: `Arrive(child: Widget, index: int, {Key? key})` — a stateful widget that animates its child in with `translateY(+16 → 0)` + `opacity(0 → 1)` + `scale(0.98 → 1)`, delayed by `index * 60ms`. When `MediaQuery.of(context).disableAnimations` is true, it renders the child immediately with no transform.

- [ ] **Step 1: Add the curve token to `jobify_motion.dart`**

Add (next to the existing curve constants):

```dart
  /// Emphasized spring for the "role arrives" entrance.
  static const Curve curveArrive = Curves.easeOutCubic;
  static const Duration durationArrive = Duration(milliseconds: 420);
  static const Duration arriveStagger = Duration(milliseconds: 60);
```

- [ ] **Step 2: Write the failing test**

Create `test/widget/widgets/arrive_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/presentation/widgets/arrive.dart';

Widget _wrap(Widget child, {bool disableAnimations = false}) => MediaQuery(
      data: MediaQueryData(disableAnimations: disableAnimations),
      child: MaterialApp(
        theme: ThemeData.light(useMaterial3: true),
        home: Scaffold(body: child),
      ),
    );

void main() {
  testWidgets('reduced motion renders child immediately, fully opaque',
      (tester) async {
    await tester.pumpWidget(
      _wrap(const Arrive(index: 3, child: Text('hi')), disableAnimations: true),
    );
    // No pumpAndSettle needed — should be visible on first frame.
    expect(find.text('hi'), findsOneWidget);
    final opacity = tester.widget<Opacity>(
      find.ancestor(of: find.text('hi'), matching: find.byType(Opacity)),
    );
    expect(opacity.opacity, 1.0);
  });

  testWidgets('with motion, child settles to visible', (tester) async {
    await tester.pumpWidget(_wrap(const Arrive(index: 0, child: Text('hi'))));
    await tester.pumpAndSettle();
    expect(find.text('hi'), findsOneWidget);
    final opacity = tester.widget<Opacity>(
      find.ancestor(of: find.text('hi'), matching: find.byType(Opacity)),
    );
    expect(opacity.opacity, 1.0);
  });
}
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && flutter test test/widget/widgets/arrive_test.dart`
Expected: FAIL — `arrive.dart` does not exist.

- [ ] **Step 4: Implement `arrive.dart`**

```dart
import 'package:flutter/material.dart';

import 'package:jobify_app/presentation/theme/jobify_motion.dart';

/// Entrance animation for "the role arrives": a child settles in from slightly
/// below, fading and scaling up, staggered by [index]. The single orchestrated
/// motion moment in the app — used on the feed (first load / refresh) and as a
/// sign-in sibling. Honors reduced motion.
class Arrive extends StatefulWidget {
  const Arrive({required this.index, required this.child, super.key});

  final int index;
  final Widget child;

  @override
  State<Arrive> createState() => _ArriveState();
}

class _ArriveState extends State<Arrive> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: JobifyMotion.durationArrive,
  );
  late final Animation<double> _t =
      CurvedAnimation(parent: _c, curve: JobifyMotion.curveArrive);

  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    if (MediaQuery.of(context).disableAnimations) {
      _c.value = 1.0; // jump to settled, no transform
    } else {
      Future<void>.delayed(JobifyMotion.arriveStagger * widget.index, () {
        if (mounted) _c.forward();
      });
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _t,
      builder: (context, child) {
        final t = _t.value;
        return Opacity(
          opacity: t,
          child: Transform.translate(
            offset: Offset(0, (1 - t) * 16),
            child: Transform.scale(scale: 0.98 + 0.02 * t, child: child),
          ),
        );
      },
      child: widget.child,
    );
  }
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && flutter test test/widget/widgets/arrive_test.dart`
Expected: PASS.

- [ ] **Step 6: Format, analyze, commit**

Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && dart format lib test && flutter analyze`
Expected: PASS.

```bash
cd /Users/ahamadshah/ahamed_personal/jobify
git add app/lib/presentation/widgets/arrive.dart app/lib/presentation/theme/jobify_motion.dart app/test/widget/widgets/arrive_test.dart
git commit -m "feat(app): Arrive entrance-motion widget (reduced-motion safe)"
```

---

## Task 5: Invert the feed card + wire the arrival stagger

**Files:**
- Modify: `lib/presentation/feed/feed_item_card.dart` (rework build)
- Modify: `lib/presentation/feed/feed_screen.dart` (wrap items in `Arrive`)
- Test: `test/widget/feed_screen_test.dart` (add sentence/caveat assertions if a card with explanation is rendered there) — otherwise add a focused `feed_item_card` test

**Interfaces:**
- Consumes: `Arrive`, `JobifyScoreBadge`, `JobifyTypography.mono`, `JobifyColors.caveat*`.
- Produces: a card whose visual order is **employer + score stamp → role title (quiet) → match sentence (hero, Inter 17/w500) → caveat (amber rule, conditional) → meta (mono)**.

- [ ] **Step 1: Write the failing test**

Add to `test/widget/feed_screen_test.dart` (or create `test/widget/widgets/feed_item_card_test.dart` if cleaner — match the existing fixture style for building a `FeedItemCard`). The test pumps a `FeedItemCard` whose `explanation.fit = 'Your Django work lines up.'` and `explanation.caveat = '3 yrs vs 5 required'`:

```dart
  testWidgets('card leads with the match sentence and shows the caveat',
      (tester) async {
    await tester.pumpWidget(_wrapCard(/* item with fit + caveat */));
    expect(find.text('Your Django work lines up.'), findsOneWidget);
    expect(find.textContaining('3 yrs vs 5 required'), findsOneWidget);
  });

  testWidgets('no caveat line when caveat is null', (tester) async {
    await tester.pumpWidget(_wrapCard(/* item with fit, caveat: null */));
    expect(find.textContaining('vs'), findsNothing);
  });
```

Build the fixture from the existing test helpers/DTO factories already used in `feed_screen_test.dart` / `job_detail_screen_test.dart` (reuse `ExplanationDto(...)`). `_wrapCard` wraps in `MaterialApp(theme: ThemeData.light(useMaterial3: true))` + a `MediaQuery(disableAnimations: true)` so `Arrive` doesn't defer the first frame.

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && flutter test test/widget/feed_screen_test.dart`
Expected: FAIL — sentence/caveat finders not matching the current bottom-buried layout.

- [ ] **Step 3: Rework `feed_item_card.dart` build**

Replace the `Column` children with the inverted hierarchy. Keep the existing `Card` + `InkWell` + `onTap` wrapper, `_ago`/`meta` helper, and the closed-job pill:

```dart
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    employer.name.toUpperCase(),
                    style: theme.textTheme.labelMedium?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                      letterSpacing: 0.4,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: JobifySpacing.sm),
                if (isClosed)
                  _ClosedPill(theme: theme)
                else if (showScore && match != null)
                  JobifyScoreBadge(score: match!.totalScore),
              ],
            ),
            const SizedBox(height: JobifySpacing.xs),
            Text(job.title, style: theme.textTheme.titleMedium),
            if (explanation != null) ...[
              const SizedBox(height: JobifySpacing.sm),
              Text(
                explanation!.fit,
                // The hero: the reason, one notch larger than the title.
                style: theme.textTheme.titleMedium?.copyWith(
                  fontSize: 17,
                  fontWeight: FontWeight.w500,
                  height: 1.4,
                  color: theme.colorScheme.onSurface,
                ),
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
              if (explanation!.caveat != null) ...[
                const SizedBox(height: JobifySpacing.sm),
                _CaveatLine(text: explanation!.caveat!),
              ],
            ],
            const SizedBox(height: JobifySpacing.md),
            Text(
              meta,
              style: JobifyTypography.mono(
                fontSize: 12,
                fontWeight: FontWeight.w400,
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
```

Add the two private widgets at the bottom of the file:

```dart
class _CaveatLine extends StatelessWidget {
  const _CaveatLine({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final amber = isDark ? JobifyColors.caveatDark : JobifyColors.caveatLight;
    return Container(
      padding: const EdgeInsets.only(left: JobifySpacing.sm),
      decoration: BoxDecoration(
        border: Border(left: BorderSide(color: amber, width: 2.5)),
      ),
      child: Text(
        'Counts against: $text',
        style: Theme.of(context).textTheme.bodySmall?.copyWith(color: amber),
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
      ),
    );
  }
}

class _ClosedPill extends StatelessWidget {
  const _ClosedPill({required this.theme});
  final ThemeData theme;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(
            horizontal: JobifySpacing.sm, vertical: JobifySpacing.xs),
        decoration: BoxDecoration(
          color: theme.colorScheme.surfaceContainerHighest,
          border: Border.all(color: theme.colorScheme.outlineVariant),
          borderRadius: JobifyRadii.borderRadiusPill,
        ),
        child: Text('Closed',
            style: theme.textTheme.labelSmall
                ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
      );
}
```

Add imports as needed: `jobify_colors.dart`, `jobify_typography.dart`, `jobify_radii.dart` (if not already imported).

- [ ] **Step 4: Wire `Arrive` into the feed list**

In `feed_screen.dart`, wrap each rendered `FeedItemCard` in `Arrive(index: i, child: ...)` where `i` is the item's index in the `ListView.separated` itemBuilder. Import `arrive.dart`. (Pagination appends are also wrapped, but their index keeps climbing so they don't re-stagger from zero — acceptable; the only visible stagger is the initial screenful.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && flutter test test/widget/feed_screen_test.dart test/widget/saved_screen_test.dart`
Expected: PASS. (Saved reuses `FeedItemCard`; confirm it still renders.)

- [ ] **Step 6: Format, analyze, commit**

Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && dart format lib test && flutter analyze`
Expected: PASS.

```bash
cd /Users/ahamadshah/ahamed_personal/jobify
git add app/lib/presentation/feed/feed_item_card.dart app/lib/presentation/feed/feed_screen.dart app/test/widget/feed_screen_test.dart
git commit -m "feat(app): invert feed card (sentence-led) + arrival stagger"
```

---

## Task 6: Sign-in screen — restyle + entrance

**Files:**
- Modify: `lib/presentation/auth/sign_in_screen.dart`
- Test: `test/widget/sign_in_screen_test.dart` (keep existing finders green)

**Interfaces:**
- Consumes: `Arrive`, `JobifyColors.brandBlue*`. Preserves the existing `kIsWeb` branch, the `_WebSignInButton`, the post-deletion snackbar, and error handling.

- [ ] **Step 1: Restyle the layout**

Change the centered column to a left-aligned composition. Keep all logic (loading state, `kIsWeb` branch, error mapping) intact. The wordmark goes brand-blue; tagline kept; mobile button becomes a bordered (outlined-style) Google button. Wrap the wordmark / tagline / button each in `Arrive(index: 0|1|2, child: ...)`:

```dart
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: JobifySpacing.xl),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Arrive(
                index: 0,
                child: Text(
                  'Jobify',
                  style: theme.textTheme.displayLarge?.copyWith(
                    color: theme.brightness == Brightness.dark
                        ? JobifyColors.brandBlueDark
                        : JobifyColors.brandBlueLight,
                  ),
                ),
              ),
              const SizedBox(height: JobifySpacing.sm),
              Arrive(
                index: 1,
                child: Text(
                  'Roles that match you, not the other way around.',
                  style: theme.textTheme.bodyLarge
                      ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                ),
              ),
              const SizedBox(height: JobifySpacing.xxl),
              Arrive(index: 2, child: /* existing button subtree */),
            ],
          ),
        ),
      ),
    );
```

For the mobile button, swap `FilledButton.icon` → `OutlinedButton.icon` (white/surface fill via theme, `line` border, ink label) so it reads as a clean, calm Google button rather than a blue-filled CTA. Keep the icon + `'Continue with Google'` / `'Signing in…'` labels exactly (the test asserts `'Continue with Google'`).

- [ ] **Step 2: Keep the sign-in test green**

Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && flutter test test/widget/sign_in_screen_test.dart`
Expected: PASS. The test pumps with `MediaQuery` — if it doesn't set `disableAnimations`, `Arrive` defers the first frame; add `await tester.pumpAndSettle()` before assertions, or wrap the test's `MediaQuery` with `disableAnimations: true`. Update the test's pump accordingly (this is a legitimate test change for the new entrance motion).

- [ ] **Step 3: Format, analyze, commit**

Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && dart format lib test && flutter analyze && flutter test test/widget/sign_in_screen_test.dart`
Expected: PASS.

```bash
cd /Users/ahamadshah/ahamed_personal/jobify
git add app/lib/presentation/auth/sign_in_screen.dart app/test/widget/sign_in_screen_test.dart
git commit -m "feat(app): Clear Sky sign-in — blue wordmark, bordered Google button, entrance"
```

---

## Task 7: Remaining screens — job detail, applications, profile, shell, shared widgets

**Files:**
- Modify: `lib/presentation/job_detail/job_detail_screen.dart` (the `_MatchCard`)
- Modify: `lib/presentation/applications/applications_screen.dart` (`_StatusPill`)
- Modify: `lib/presentation/profile/profile_screen.dart` (mono data, section headers)
- Modify: `lib/presentation/widgets/jobify_shell_scaffold.dart` + `jobify_recruiter_shell_scaffold.dart` (nav)
- Modify: `lib/presentation/widgets/jobify_empty_state.dart`, `jobify_loading_view.dart`, `jobify_error_view.dart` (token sanity)
- Tests: keep `job_detail_screen_test.dart`, `applications_screen_test.dart`, `profile_screen_test.dart`, shell tests green

**Interfaces:**
- Consumes: tokens/typography from Tasks 1–2; `JobifyScoreBadge` from Task 3.

- [ ] **Step 1: Job detail `_MatchCard` — sentence-led**

Mirror the feed card hierarchy: keep the "Why this match" title + `JobifyScoreBadge`, but render `exp.fit` as the hero (titleMedium @ 17/w500/onSurface), the caveat via the same amber-rule treatment (extract `_CaveatLine` into a shared spot or duplicate the small widget), and the generator label in `JobifyTypography.mono(fontSize: 11, color: onSurfaceVariant)`. Do not change the `find.text('Why this match')` string (tests + golden_path assert it).

- [ ] **Step 2: Applications `_StatusPill`**

- Applied: `colorScheme.primaryContainer` bg (= brandTint) + `colorScheme.onPrimaryContainer` text (= brand) — now reads blue, the active/positive meaning.
- Withdrawn: `colorScheme.surfaceContainerHighest` bg + `colorScheme.onSurfaceVariant` text (muted). Keep pill shape.
- Dates: switch the "Applied <date>" / "Withdrawn <date>" line to `JobifyTypography.mono(fontSize: 12, color: onSurfaceVariant)`.

- [ ] **Step 3: Profile — mono data + Schibsted section headers**

- Section headers ("Account", "Appearance") already use `titleMedium` → now Inter; bump to `headlineMedium` (Schibsted) for a calmer editorial divider if it reads better — optional, keep if it doesn't crowd.
- `_DetailRow` values that are data (CTC ₹, experience, notice period) → `JobifyTypography.mono(fontSize: 14, color: onSurface)`. Labels stay Inter `bodyMedium` muted.
- App-version footer → mono.

- [ ] **Step 4: Nav shells — brand-blue selection**

In both shell scaffolds, set `NavigationBar`'s `backgroundColor: colorScheme.surfaceContainerHighest` (or `paper2` via a token), `indicatorColor: colorScheme.primaryContainer` (brandTint), and rely on M3 selected-state coloring (icon/label use `primary`). Confirm unselected uses `onSurfaceVariant`. If the current code hardcodes any color, replace with the token.

- [ ] **Step 5: Shared empty/loading/error widgets**

Sanity pass — ensure icons/text pull from `colorScheme.onSurfaceVariant` / `error` (no leftover warm literals). The error icon uses `colorScheme.error` (= danger). No structural change.

- [ ] **Step 6: Run the affected widget tests**

Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && flutter test test/widget/job_detail_screen_test.dart test/widget/applications_screen_test.dart test/widget/profile_screen_test.dart test/widget/recruiter_shell_scaffold_test.dart`
Expected: PASS. Fix any assertion that referenced an old color/structure (update to the new token, don't weaken the test).

- [ ] **Step 7: Format, analyze, commit**

Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && dart format lib test && flutter analyze`
Expected: PASS.

```bash
cd /Users/ahamadshah/ahamed_personal/jobify
git add app/lib/presentation/job_detail app/lib/presentation/applications app/lib/presentation/profile app/lib/presentation/widgets
git commit -m "feat(app): Clear Sky pass — job detail, applications, profile, nav, shared widgets"
```

---

## Task 8: Full-suite + dark-mode + recruiter sanity sweep

**Files:** none new — verification + targeted fixes only.

- [ ] **Step 1: Run the full CI trio**

Run: `cd /Users/ahamadshah/ahamed_personal/jobify/app && dart format --set-exit-if-changed lib test && flutter analyze && flutter test`
Expected: all PASS. Fix any remaining test fallout (color/structure assertions) by updating the assertion to the new design — never by weakening a behavioral check.

- [ ] **Step 2: Dark-mode visual sweep**

Run the app (`flutter run`), toggle Profile → Appearance → Dark. Walk: sign-in, feed (watch the arrival stagger once), a card with a caveat, job detail match card, applications (Applied + Withdrawn pills), profile, nav bar. Confirm:
- No invisible text (no hardcoded near-white/near-dark inside brand/caveat fills).
- Brand blue and amber are the only chromatic colors; everything else is ink-on-sky.
- The score stamp reads brand-blue only on strong (≥80%) matches.

- [ ] **Step 3: Recruiter sanity sweep**

As a recruiter (or via the recruiter shell route), open dashboard, jobs list, job detail, applicants, employer, profile in **both** themes. These inherited the new tokens — confirm nothing renders an off-palette color or an unreadable contrast. Fix any hardcoded literal found (replace with the matching token).

- [ ] **Step 4: Reduced-motion check**

Enable the OS "reduce motion" setting (or pump a widget test path), open the feed, and confirm cards appear instantly with no slide/scale.

- [ ] **Step 5: Final commit (if Steps 2–4 needed fixes)**

```bash
cd /Users/ahamadshah/ahamed_personal/jobify
git add app/
git commit -m "fix(app): Clear Sky dark-mode + recruiter sanity sweep"
```

---

## Self-Review

**Spec coverage:**
- Token system (light+dark, rationed color) → Task 1. ✓
- Typography (Schibsted/Inter/IBM Plex Mono + scale) → Task 2. ✓
- Score demoted to two-state mono stamp; bands retired → Task 3. ✓
- "The role arrives" motion + reduced-motion → Task 4 (widget), wired in Tasks 5–6. ✓
- Inverted sentence-led card + amber caveat rule → Task 5. ✓
- Sign-in restyle (blue wordmark, bordered button, entrance) → Task 6. ✓
- Per-screen application (job detail, applications, profile, nav, shared) → Task 7. ✓
- Both-themes + recruiter inheritance verification → Task 8. ✓
- Global token replacement (not fork) → Task 1 replaces values in place. ✓

**Placeholder scan:** Task 7 uses directed prose ("mirror the feed card hierarchy", exact token names) rather than full code for each screen because they're small, repetitive token swaps over existing structure; every step names the exact file, widget, and token. No "add error handling"/"TBD" placeholders. The testable tasks (1–6) carry complete code.

**Type consistency:** `JobifyScoreBadge.isStrong` (Task 3) used in Task 3 tests; `Arrive(index:, child:)` (Task 4) used identically in Tasks 5–6; `JobifyTypography.mono(...)` signature defined in Task 2, consumed in Tasks 3/5/7; token names (`brandBlue*`, `caveat*`, `inkSoft*`) consistent across Tasks 1/3/5. ✓

**Note on TDD scope:** pure-visual styling (typography families, per-screen token swaps) can't be meaningfully unit-tested (`buildTheme`/`google_fonts` can't run in CI), so those tasks gate on `flutter analyze` + the Task 8 visual sweep. Genuinely testable logic — token values, the 0.80 score threshold, caveat conditional rendering, reduced-motion — is covered by failing-first tests.
