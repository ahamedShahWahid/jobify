import 'package:flutter/material.dart';

import 'package:kpa_app/presentation/theme/kpa_spacing.dart';
import 'package:kpa_app/presentation/widgets/kpa_empty_state.dart';

class RecruiterEmployerScreen extends StatelessWidget {
  const RecruiterEmployerScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Padding(
        padding: EdgeInsets.all(KpaSpacing.lg),
        child: KpaEmptyState(
          headline: 'Team management',
          body: 'Inviting teammates and managing your company comes in a '
              'later release.',
          icon: Icons.business_outlined,
        ),
      ),
    );
  }
}
