import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'screens/home_screen.dart';

void main() {
  runApp(const ReaderApp());
}

class ReaderApp extends StatelessWidget {
  const ReaderApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Reading Assistant',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0F6CBD)),
        textTheme: GoogleFonts.merriweatherTextTheme(),
        useMaterial3: true,
      ),
      home: const HomeScreen(),
    );
  }
}
