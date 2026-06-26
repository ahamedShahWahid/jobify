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
