import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:file_picker/file_picker.dart';

const String apiBaseUrl = 'https://awaken-vice-running.ngrok-free.dev';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const EmployeePortalApp());
}

class EmployeePortalApp extends StatelessWidget {
  const EmployeePortalApp({super.key});

  static const navy = Color(0xFF5C1524);
  static const navyLight = Color(0xFF7A1F32);
  static const gold = Color(0xFFC9A24B);
  static const goldSoft = Color(0xFFE9D9AE);
  static const paper = Color(0xFFF7F4EC);
  static const green = Color(0xFF2F7A4F);
  static const red = Color(0xFFB14A3D);
  static const gray = Color(0xFF6B7280);
  static const line = Color(0xFFDFD9C8);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'بوابة الموظفين',
      theme: ThemeData(
        useMaterial3: true,
        fontFamily: 'Cairo',
        colorScheme: ColorScheme.fromSeed(
          seedColor: navy,
          brightness: Brightness.light,
          primary: navy,
          secondary: gold,
          surface: const Color(0xFFFFFDF8),
        ),
        scaffoldBackgroundColor: const Color(0xFFF7F2E8),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF4A0D19),
          foregroundColor: Colors.white,
          centerTitle: true,
          elevation: 0,
        ),
        cardTheme: CardThemeData(
          color: const Color(0xFFFFFDF8),
          elevation: 3,
          shadowColor: const Color(0x33000000),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
            side: const BorderSide(color: Color(0x33C9A24B)),
          ),
        ),
        navigationBarTheme: NavigationBarThemeData(
          backgroundColor: Color(0xFF6B1023),
          indicatorColor: const Color(0x33C9A24B),
          labelTextStyle: WidgetStateProperty.resolveWith(
            (states) => TextStyle(
              color: states.contains(WidgetState.selected) ? gold : Colors.white70,
              fontWeight: states.contains(WidgetState.selected)
                  ? FontWeight.w900
                  : FontWeight.w600,
              fontSize: 11,
            ),
          ),
          iconTheme: WidgetStateProperty.resolveWith(
            (states) => IconThemeData(
              color: states.contains(WidgetState.selected) ? gold : Colors.white70,
            ),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: const Color(0xFFFFFDF8),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(color: line),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(color: line),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(color: gold, width: 1.6),
          ),
        ),
      ),
      home: const LoginPage(),
    );
  }
}

class ApiClient {
  String? token;

  Map<String, String> get headers => {
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
        'ngrok-skip-browser-warning': 'true',
      };

  Future<http.Response> post(
    String path,
    Map<String, dynamic> body,
  ) {
    return http.post(
      Uri.parse('$apiBaseUrl$path'),
      headers: headers,
      body: jsonEncode(body),
    ).timeout(const Duration(seconds: 25));
  }

  Future<http.Response> get(String path) {
    return http.get(
      Uri.parse('$apiBaseUrl$path'),
      headers: headers,
    ).timeout(const Duration(seconds: 25));
  }

  Future<http.Response> put(
    String path,
    Map<String, dynamic> body,
  ) {
    return http.put(
      Uri.parse('$apiBaseUrl$path'),
      headers: headers,
      body: jsonEncode(body),
    ).timeout(const Duration(seconds: 25));
  }

  Future<http.Response> delete(String path) {
    return http.delete(
      Uri.parse('$apiBaseUrl$path'),
      headers: headers,
    ).timeout(const Duration(seconds: 25));
  }
}

final api = ApiClient();
final ValueNotifier<int> profilePhotoRevision = ValueNotifier<int>(0);

String cleanError(dynamic error) {
  return error.toString().replaceFirst('Exception: ', '');
}

double toDouble(dynamic value) {
  if (value is num) return value.toDouble();
  return double.tryParse('$value') ?? 0.0;
}

String money(dynamic value) {
  return toDouble(value).toStringAsFixed(2);
}

class SplashPage extends StatefulWidget {
  const SplashPage({super.key});

  @override
  State<SplashPage> createState() => _SplashPageState();
}

class _SplashPageState extends State<SplashPage> {
  @override
  void initState() {
    super.initState();

    Future.delayed(const Duration(milliseconds: 1400), () async {
      final prefs = await SharedPreferences.getInstance();

      final token = prefs.getString('token');
      final name = prefs.getString('full_name');
      final code = prefs.getString('employee_code');
      final role = prefs.getString('role') ?? 'employee';

      if (!mounted) return;

      if (token != null && token.isNotEmpty) {
        api.token = token;

        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => HomePage(
              fullName: name ?? '',
              employeeCode: code ?? '',
              role: role,
            ),
          ),
        );
      } else {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => const CinematicIntroPage(),
          ),
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: EmployeePortalApp.navy,
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.account_balance,
              color: EmployeePortalApp.gold,
              size: 64,
            ),
            SizedBox(height: 18),
            Text(
              'Payroll Portal',
              style: TextStyle(
                color: Colors.white,
                fontSize: 25,
                fontWeight: FontWeight.w800,
              ),
            ),
            SizedBox(height: 8),
            Text(
              'بوابة الموظفين',
              style: TextStyle(
                color: Color(0xFFEAD8A5),
                fontSize: 15,
              ),
            ),
            SizedBox(height: 28),
            CircularProgressIndicator(
              color: EmployeePortalApp.gold,
            ),
          ],
        ),
      ),
    );
  }
}


class _ExactCompanyLogo extends StatelessWidget {
  final double size;
  const _ExactCompanyLogo({this.size = 42});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: ClipOval(
        child: Image.asset(
          'assets/delta_logo.png',
          fit: BoxFit.cover,
          filterQuality: FilterQuality.high,
        ),
      ),
    );
  }
}

class CinematicIntroPage extends StatelessWidget {
  const CinematicIntroPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        backgroundColor: Colors.black,
        body: Stack(
          fit: StackFit.expand,
          children: [
            Image.asset('assets/industrial/scene_intro.png', fit: BoxFit.cover),
            const DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Color(0x22000000), Color(0x00000000), Color(0xB8000000)],
                ),
              ),
            ),
            SafeArea(
              child: Column(
                children: [
                  const Spacer(),
                  Container(
                    margin: const EdgeInsets.all(22),
                    padding: const EdgeInsets.fromLTRB(20, 18, 20, 16),
                    decoration: BoxDecoration(
                      color: const Color(0xD9080B0E),
                      borderRadius: BorderRadius.circular(22),
                      border: Border.all(color: EmployeePortalApp.gold.withValues(alpha: .75)),
                    ),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const _ExactCompanyLogo(size: 72),
                        const SizedBox(height: 8),
                        const Text('الشركة المصرية لنقل الكهرباء', textAlign: TextAlign.center,
                          style: TextStyle(color: Colors.white, fontSize: 19, fontWeight: FontWeight.w900)),
                        const Text('منطقة الدلتا', style: TextStyle(color: EmployeePortalApp.gold, fontSize: 16, fontWeight: FontWeight.w900)),
                        const SizedBox(height: 14),
                        SizedBox(
                          width: double.infinity,
                          child: FilledButton.icon(
                            onPressed: () => Navigator.pushReplacement(context,
                              MaterialPageRoute(builder: (_) => const _IndustrialSwitchGatePage())),
                            icon: const Icon(Icons.electric_bolt_rounded),
                            label: const Text('ابدأ تشغيل النظام'),
                            style: FilledButton.styleFrom(
                              backgroundColor: EmployeePortalApp.navy,
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(vertical: 14),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _IndustrialSwitchGatePage extends StatefulWidget {
  const _IndustrialSwitchGatePage();
  @override
  State<_IndustrialSwitchGatePage> createState() => _IndustrialSwitchGatePageState();
}

class _IndustrialSwitchGatePageState extends State<_IndustrialSwitchGatePage> {
  bool on = false;

  Future<void> _activate() async {
    if (on) return;
    setState(() => on = true);
    await Future.delayed(const Duration(milliseconds: 900));
    if (!mounted) return;
    Navigator.pushReplacement(context, PageRouteBuilder(
      transitionDuration: const Duration(milliseconds: 650),
      pageBuilder: (_, a, __) => FadeTransition(opacity: a, child: const LoginPage()),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        backgroundColor: Colors.black,
        body: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: _activate,
          onVerticalDragEnd: (d) { if ((d.primaryVelocity ?? 0) > 0) _activate(); },
          child: Stack(
            fit: StackFit.expand,
            children: [
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 350),
                child: Image.asset(
                  on ? 'assets/industrial/switch_on.png' : 'assets/industrial/switch_off.png',
                  key: ValueKey(on), fit: BoxFit.cover,
                ),
              ),
              if (on)
                IgnorePointer(child: Container(decoration: const BoxDecoration(
                  gradient: RadialGradient(center: Alignment.center, radius: .75,
                    colors: [Color(0x55FFC04A), Colors.transparent])))),
              SafeArea(
                child: Column(
                  children: [
                    const SizedBox(height: 18),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
                      decoration: BoxDecoration(color: const Color(0xC9080B0E), borderRadius: BorderRadius.circular(18),
                        border: Border.all(color: EmployeePortalApp.gold.withValues(alpha: .7))),
                      child: Text(on ? 'تم تشغيل النظام بنجاح' : 'المفتاح الرئيسي',
                        style: const TextStyle(color: EmployeePortalApp.goldSoft, fontSize: 17, fontWeight: FontWeight.w900)),
                    ),
                    const Spacer(),
                    Container(
                      margin: const EdgeInsets.all(24),
                      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                      decoration: BoxDecoration(color: const Color(0xD9080B0E), borderRadius: BorderRadius.circular(18),
                        border: Border.all(color: EmployeePortalApp.gold.withValues(alpha: .65))),
                      child: Text(on ? '⚡ جاري الانتقال إلى بوابة الموظفين...' : '⚡ اسحب المفتاح لأسفل أو اضغط لتشغيل النظام',
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w800)),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final code = TextEditingController();
  final password = TextEditingController();

  bool loading = false;
  bool hidePassword = true;
  bool lightOn = false;
  bool rememberMe = false;
  String? error;

  @override
  void initState() {
    super.initState();
    _loadRememberedEmployee();
  }

  Future<void> _loadRememberedEmployee() async {
    final prefs = await SharedPreferences.getInstance();
    final remembered = prefs.getBool('remember_me') ?? false;
    final employeeCode = prefs.getString('remembered_employee_code') ?? '';
    if (!mounted) return;
    setState(() {
      rememberMe = remembered;
      if (remembered && employeeCode.isNotEmpty) {
        code.text = employeeCode;
      }
    });
  }

  Future<void> _saveRememberMe() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('remember_me', rememberMe);
    if (rememberMe) {
      await prefs.setString('remembered_employee_code', code.text.trim());
    } else {
      await prefs.remove('remembered_employee_code');
    }
  }

  void _turnLightOn() {
    if (lightOn) return;
    setState(() => lightOn = true);
  }

  Future<void> login() async {
    FocusScope.of(context).unfocus();

    if (code.text.trim().isEmpty || password.text.isEmpty) {
      setState(() => error = 'من فضلك أدخل كود الموظف وكلمة المرور.');
      return;
    }

    setState(() {
      loading = true;
      error = null;
    });

    try {
      final response = await api.post('/api/login', {
        'employee_code': code.text.trim(),
        'password': password.text,
      });

      final dynamic decoded = jsonDecode(response.body);
      final data = decoded is Map ? Map<String, dynamic>.from(decoded) : <String, dynamic>{};

      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw Exception(data['error'] ?? 'فشل تسجيل الدخول');
      }

      await _saveRememberMe();

      if (!mounted) return;

      if (data['must_change_password'] == true) {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => FirstLoginSetupPage(
              employeeCode: '${data['employee_code'] ?? code.text.trim()}',
              currentPassword: password.text,
            ),
          ),
        );
        return;
      }

      if (data['must_complete_profile'] == true) {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => CompleteProfilePage(
              employeeCode: '${data['employee_code'] ?? code.text.trim()}',
              currentPassword: password.text,
            ),
          ),
        );
        return;
      }

      await _saveSessionAndOpen(context, data);
    } catch (e) {
      if (mounted) setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  void dispose() {
    code.dispose();
    password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        backgroundColor: Colors.black,
        body: Stack(
          fit: StackFit.expand,
          children: [
            Image.asset('assets/industrial/login_bg_sunset_final.png', fit: BoxFit.cover),
            const DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Color(0x44000000), Color(0x22000000), Color(0x88000000)],
                ),
              ),
            ),
            SafeArea(
              child: Center(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(22),
                  child: Container(
                    constraints: const BoxConstraints(maxWidth: 410),
                    padding: const EdgeInsets.fromLTRB(22, 22, 22, 18),
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        colors: [Color(0xF2770C22), Color(0xF24A0916)],
                      ),
                      borderRadius: BorderRadius.circular(22),
                      border: Border.all(color: EmployeePortalApp.gold.withValues(alpha: .78)),
                      boxShadow: const [BoxShadow(color: Color(0x99000000), blurRadius: 30, offset: Offset(0, 14))],
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Center(child: _ExactCompanyLogo(size: 82)),
                        const SizedBox(height: 8),
                        const Text('بوابة الموظفين', textAlign: TextAlign.center,
                          style: TextStyle(color: EmployeePortalApp.goldSoft, fontSize: 27, fontWeight: FontWeight.w900)),
                        const SizedBox(height: 5),
                        const Text('الشركة المصرية لنقل الكهرباء', textAlign: TextAlign.center,
                          style: TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w800)),
                        const Text('منطقة الدلتا', textAlign: TextAlign.center,
                          style: TextStyle(color: EmployeePortalApp.gold, fontSize: 14, fontWeight: FontWeight.w900)),
                        const SizedBox(height: 20),
                        TextField(
                          controller: code,
                          keyboardType: TextInputType.number,
                          style: const TextStyle(color: Colors.white),
                          decoration: _industrialInput('اسم المستخدم', Icons.person_rounded),
                        ),
                        const SizedBox(height: 12),
                        TextField(
                          controller: password,
                          obscureText: hidePassword,
                          onSubmitted: (_) => login(),
                          style: const TextStyle(color: Colors.white),
                          decoration: _industrialInput('كلمة المرور', Icons.lock_rounded).copyWith(
                            suffixIcon: IconButton(
                              onPressed: () => setState(() => hidePassword = !hidePassword),
                              icon: Icon(hidePassword ? Icons.visibility_rounded : Icons.visibility_off_rounded,
                                color: EmployeePortalApp.goldSoft),
                            ),
                          ),
                        ),
                        Row(
                          children: [
                            Checkbox(value: rememberMe, activeColor: EmployeePortalApp.navy,
                              onChanged: (v) => setState(() => rememberMe = v ?? false)),
                            const Text('تذكر كود الموظف', style: TextStyle(color: Color(0xFFD8D1C4), fontSize: 12)),
                          ],
                        ),
                        if (error != null) ...[
                          Text(error!, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFFFF8A80), fontWeight: FontWeight.w700)),
                          const SizedBox(height: 10),
                        ],
                        SizedBox(
                          height: 52,
                          child: FilledButton(
                            onPressed: loading ? null : login,
                            style: FilledButton.styleFrom(backgroundColor: EmployeePortalApp.gold, foregroundColor: EmployeePortalApp.navy,
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8))),
                            child: loading
                              ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white))
                              : const Text('تسجيل الدخول', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: EmployeePortalApp.navy)),
                          ),
                        ),
                        TextButton(
                          onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ForgotPasswordPage())),
                          child: const Text('نسيت كلمة المرور؟', style: TextStyle(color: EmployeePortalApp.goldSoft)),
                        ),
                        const SizedBox(height: 4),
                        const Text(
                          'تصميم وبرمجة: خالد يوسف المنسي',
                          textAlign: TextAlign.center,
                          style: TextStyle(color: Color(0xFFB9B2A7), fontSize: 10.5, fontWeight: FontWeight.w700),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  InputDecoration _industrialInput(String hint, IconData icon) {
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(color: Color(0xFFB9B2A7)),
      prefixIcon: Icon(icon, color: EmployeePortalApp.goldSoft),
      filled: true,
      fillColor: const Color(0xCC2A0B13),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: Color(0xFF6E6557))),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: EmployeePortalApp.gold, width: 1.4)),
    );
  }
}


class _IndustrialLoginBackgroundPainter extends CustomPainter {
  const _IndustrialLoginBackgroundPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final bg = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [Color(0xFF111820), Color(0xFF080B0E), Color(0xFF030506)],
      ).createShader(Offset.zero & size);
    canvas.drawRect(Offset.zero & size, bg);

    // Sunset glow behind the transmission towers.
    final sunset = Paint()
      ..shader = RadialGradient(
        center: const Alignment(-.45, .25),
        radius: .8,
        colors: [
          const Color(0xFFB76A2A).withValues(alpha: .42),
          const Color(0xFF5C1524).withValues(alpha: .16),
          Colors.transparent,
        ],
      ).createShader(Offset.zero & size);
    canvas.drawRect(Offset.zero & size, sunset);

    final tower = Paint()
      ..color = const Color(0xFF050708).withValues(alpha: .82)
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke;
    void drawTower(double cx, double baseY, double scale) {
      final topY = baseY - 250 * scale;
      canvas.drawLine(Offset(cx, topY), Offset(cx - 55 * scale, baseY), tower);
      canvas.drawLine(Offset(cx, topY), Offset(cx + 55 * scale, baseY), tower);
      canvas.drawLine(Offset(cx - 55 * scale, baseY), Offset(cx + 55 * scale, baseY), tower);
      for (int i = 1; i <= 5; i++) {
        final y = topY + i * 42 * scale;
        final half = 10 + i * 8 * scale;
        canvas.drawLine(Offset(cx - half, y), Offset(cx + half, y), tower);
      }
      for (final dy in [48.0, 82.0]) {
        final y = topY + dy * scale;
        canvas.drawLine(Offset(cx - 58 * scale, y), Offset(cx + 58 * scale, y), tower);
        canvas.drawLine(Offset(cx - 58 * scale, y), Offset(cx - 72 * scale, y + 10 * scale), tower);
        canvas.drawLine(Offset(cx + 58 * scale, y), Offset(cx + 72 * scale, y + 10 * scale), tower);
      }
    }
    drawTower(size.width * .16, size.height * .92, .72);
    drawTower(size.width * .84, size.height * .94, .9);

    // Industrial wall seams and vignette.
    final seam = Paint()..color = const Color(0xFFB68A45).withValues(alpha: .10);
    for (double x = 0; x < size.width; x += 72) {
      canvas.drawRect(Rect.fromLTWH(x, 0, 1, size.height), seam);
    }
    final vignette = Paint()
      ..shader = RadialGradient(
        radius: .9,
        colors: [Colors.transparent, Colors.black.withValues(alpha: .72)],
        stops: const [.45, 1],
      ).createShader(Offset.zero & size);
    canvas.drawRect(Offset.zero & size, vignette);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

InputDecoration _industrialLoginInputDecoration(String label, IconData icon) {
  return InputDecoration(
    labelText: label,
    labelStyle: const TextStyle(color: Color(0xFFBDB7AD)),
    prefixIcon: Icon(icon, color: const Color(0xFFD4C7AF)),
    filled: true,
    fillColor: const Color(0xB315181B),
    border: OutlineInputBorder(borderRadius: BorderRadius.circular(9)),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(9),
      borderSide: const BorderSide(color: Color(0xFF6E665C), width: 1.2),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(9),
      borderSide: const BorderSide(color: EmployeePortalApp.gold, width: 1.6),
    ),
  );
}

class _PowerSwitch extends StatefulWidget {
  final bool isOn;
  final VoidCallback onSwitch;

  const _PowerSwitch({
    required this.isOn,
    required this.onSwitch,
  });

  @override
  State<_PowerSwitch> createState() => _PowerSwitchState();
}

class _PowerSwitchState extends State<_PowerSwitch> {
  double dragY = 0;

  void _activate() {
    if (!widget.isOn) widget.onSwitch();
  }

  @override
  Widget build(BuildContext context) {
    final handleProgress = widget.isOn ? 1.0 : (dragY / 72.0).clamp(0.0, 1.0);

    return SizedBox(
      height: 385,
      child: Center(
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: _activate,
          onVerticalDragUpdate: (details) {
            if (widget.isOn) return;
            setState(() {
              dragY = (dragY + details.delta.dy).clamp(0.0, 72.0);
            });
          },
          onVerticalDragEnd: (_) {
            if (dragY > 28) _activate();
            if (mounted) setState(() => dragY = 0);
          },
          child: TweenAnimationBuilder<double>(
            tween: Tween<double>(begin: 0, end: handleProgress),
            duration: dragY == 0
                ? const Duration(milliseconds: 420)
                : Duration.zero,
            curve: Curves.easeOutCubic,
            builder: (context, progress, child) {
              return CustomPaint(
                size: const Size(292, 360),
                painter: _IndustrialSwitchPainter(
                  progress: progress,
                  isOn: widget.isOn,
                ),
                child: const SizedBox(width: 292, height: 360),
              );
            },
          ),
        ),
      ),
    );
  }
}

class _IndustrialSwitchPainter extends CustomPainter {
  final double progress;
  final bool isOn;

  const _IndustrialSwitchPainter({
    required this.progress,
    required this.isOn,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    // Background shadow behind the whole electrical cabinet.
    final shadow = Paint()
      ..color = const Color(0x99000000)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 18);
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(24, 28, w - 48, h - 36),
        const Radius.circular(22),
      ),
      shadow,
    );

    // Four steel conduits entering the cabinet.
    for (var i = 0; i < 4; i++) {
      final x = 76.0 + (i * 38.0);
      final pipe = Rect.fromLTWH(x, 0, 22, 52);
      final pipePaint = Paint()
        ..shader = const LinearGradient(
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
          colors: [
            Color(0xFF090909),
            Color(0xFF47413B),
            Color(0xFF11100F),
          ],
        ).createShader(pipe);
      canvas.drawRRect(
        RRect.fromRectAndRadius(pipe, const Radius.circular(6)),
        pipePaint,
      );
      canvas.drawRect(
        Rect.fromLTWH(x - 2, 34, 26, 7),
        Paint()..color = const Color(0xFF171513),
      );
    }

    final plateRect = Rect.fromLTWH(32, 38, w - 64, h - 52);
    final plate = RRect.fromRectAndRadius(plateRect, const Radius.circular(22));
    final platePaint = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          Color(0xFF4A443E),
          Color(0xFF1E1B18),
          Color(0xFF0C0B0A),
          Color(0xFF2D2823),
        ],
        stops: [0, .28, .72, 1],
      ).createShader(plateRect);
    canvas.drawRRect(plate, platePaint);

    // Double metal rim.
    canvas.drawRRect(
      plate,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.4
        ..color = const Color(0xFF9D7A4B),
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        plateRect.deflate(6),
        const Radius.circular(18),
      ),
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1
        ..color = const Color(0xFF594735),
    );

    // Subtle deterministic scratches / age marks.
    final scratch = Paint()
      ..strokeWidth = .8
      ..color = const Color(0x446C5B49);
    for (var i = 0; i < 24; i++) {
      final y = 62.0 + ((i * 13) % 250);
      final x = 48.0 + ((i * 29) % 180);
      canvas.drawLine(
        Offset(x, y),
        Offset(x + 10 + (i % 4) * 4, y - 2 + (i % 3)),
        scratch,
      );
    }

    // Corner bolts.
    for (final p in <Offset>[
      const Offset(50, 58),
      Offset(w - 50, 58),
      Offset(50, h - 32),
      Offset(w - 50, h - 32),
    ]) {
      _drawBolt(canvas, p);
    }

    // Brass title plaque.
    final titleRect = Rect.fromLTWH(76, 62, w - 152, 40);
    canvas.drawRRect(
      RRect.fromRectAndRadius(titleRect, const Radius.circular(5)),
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF3F3327), Color(0xFF17120F)],
        ).createShader(titleRect),
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(titleRect, const Radius.circular(5)),
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5
        ..color = const Color(0xFFA07C45),
    );
    _text(canvas, 'المفتاح الرئيسي',
        Offset(w / 2, 82), 15, const Color(0xFFE3C98E), FontWeight.w800);

    // OFF indicator.
    final offActive = progress < .52;
    _indicator(
      canvas,
      center: Offset(w / 2, 126),
      text: 'OFF',
      active: offActive,
      activeColor: const Color(0xFFE24635),
    );

    // Recessed handle track.
    final slotRect = Rect.fromLTWH(w / 2 - 48, 146, 96, 122);
    canvas.drawRRect(
      RRect.fromRectAndRadius(slotRect, const Radius.circular(9)),
      Paint()..color = const Color(0xFF050505),
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(slotRect, const Radius.circular(9)),
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..color = const Color(0xFF65503C),
    );

    // Dark green energized interior appears as the lever drops.
    final glowRect = Rect.fromLTWH(w / 2 - 32, 190, 64, 66);
    canvas.drawRRect(
      RRect.fromRectAndRadius(glowRect, const Radius.circular(6)),
      Paint()
        ..shader = RadialGradient(
          colors: [
            Color.lerp(const Color(0xFF081109), const Color(0xFF416D31), progress)!,
            const Color(0xFF060806),
          ],
        ).createShader(glowRect),
    );

    // Heavy pivot pin.
    _metalCylinder(canvas, Rect.fromLTWH(w / 2 - 38, 154, 76, 24));

    // Lever: starts high and swings / drops to ON.
    final topY = 170.0 + (progress * 54.0);
    final bottomY = 238.0 + (progress * 28.0);
    final shaftPath = Path()
      ..moveTo(w / 2 - 12, topY)
      ..lineTo(w / 2 + 12, topY)
      ..lineTo(w / 2 + 18, bottomY)
      ..lineTo(w / 2 - 18, bottomY)
      ..close();
    final shaftRect = Rect.fromLTRB(w / 2 - 18, topY, w / 2 + 18, bottomY);
    canvas.drawPath(
      shaftPath,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
          colors: [
            Color(0xFF35150E),
            Color(0xFFB64B2F),
            Color(0xFF5A2114),
            Color(0xFF1D1713),
          ],
        ).createShader(shaftRect),
    );
    canvas.drawPath(
      shaftPath,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5
        ..color = const Color(0xFFB08356),
    );

    // Worn handle bands.
    canvas.drawRect(
      Rect.fromLTWH(w / 2 - 17, topY + 18, 34, 6),
      Paint()..color = const Color(0xFF25201B),
    );
    canvas.drawRect(
      Rect.fromLTWH(w / 2 - 18, bottomY - 15, 36, 7),
      Paint()..color = const Color(0xFF1C1916),
    );

    // Heavy lower grip / hammer-like end.
    final gripRect = Rect.fromLTWH(w / 2 - 38, bottomY - 2, 76, 28);
    _metalCylinder(canvas, gripRect);

    // ON lamp / status.
    _indicator(
      canvas,
      center: Offset(w / 2, 299),
      text: 'ON',
      active: progress > .74,
      activeColor: const Color(0xFF83D84D),
    );

    // Right-side brass feed plaque.
    final sideRect = Rect.fromLTWH(w - 90, 182, 54, 73);
    canvas.drawRRect(
      RRect.fromRectAndRadius(sideRect, const Radius.circular(5)),
      Paint()..color = const Color(0xFF221B15),
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(sideRect, const Radius.circular(5)),
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.2
        ..color = const Color(0xFF8E6D3E),
    );
    _text(canvas, 'لوحة', Offset(w - 63, 199), 10,
        const Color(0xFFD6B574), FontWeight.w700);
    _text(canvas, 'التغذية', Offset(w - 63, 216), 9.5,
        const Color(0xFFD6B574), FontWeight.w700);
    _text(canvas, 'الرئيسية', Offset(w - 63, 233), 9.5,
        const Color(0xFFD6B574), FontWeight.w700);

    // Left warning plate, matching the demo composition.
    final warningRect = Rect.fromLTWH(38, 176, 55, 95);
    canvas.drawRRect(
      RRect.fromRectAndRadius(warningRect, const Radius.circular(6)),
      Paint()..color = const Color(0xFF171411),
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(warningRect, const Radius.circular(6)),
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.2
        ..color = const Color(0xFF66503B),
    );
    _text(canvas, 'تحذير', const Offset(65.5, 191), 10.5,
        const Color(0xFFE1B966), FontWeight.w800);
    _text(canvas, '⚡', const Offset(65.5, 218), 23,
        const Color(0xFFD6A83F), FontWeight.w900);
    _text(canvas, 'جهد عالي', const Offset(65.5, 246), 9,
        const Color(0xFFE4C27A), FontWeight.w700);
    _text(canvas, 'خطر', const Offset(65.5, 262), 10,
        const Color(0xFFD84B3F), FontWeight.w900);

    // Energized flash glow.
    if (isOn || progress > .82) {
      final glow = Paint()
        ..color = const Color(0x55FFD46A)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 16);
      canvas.drawCircle(Offset(w / 2, 298), 34, glow);
    }
  }

  void _drawBolt(Canvas canvas, Offset c) {
    canvas.drawCircle(c, 8, Paint()..color = const Color(0xFF090807));
    canvas.drawCircle(
      c,
      7,
      Paint()
        ..shader = const RadialGradient(
          center: Alignment(-.35, -.4),
          colors: [Color(0xFF8A7968), Color(0xFF27231F), Color(0xFF090807)],
        ).createShader(Rect.fromCircle(center: c, radius: 7)),
    );
    canvas.drawLine(
      Offset(c.dx - 4, c.dy + 1),
      Offset(c.dx + 4, c.dy - 1),
      Paint()
        ..strokeWidth = 1.4
        ..color = const Color(0xFF15110E),
    );
  }

  void _metalCylinder(Canvas canvas, Rect rect) {
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, const Radius.circular(10)),
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Color(0xFF171513),
            Color(0xFF75695C),
            Color(0xFF2D2925),
            Color(0xFF0B0A09),
          ],
        ).createShader(rect),
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, const Radius.circular(10)),
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.3
        ..color = const Color(0xFF9C7A50),
    );
  }

  void _indicator(
    Canvas canvas, {
    required Offset center,
    required String text,
    required bool active,
    required Color activeColor,
  }) {
    final rect = Rect.fromCenter(center: center, width: 82, height: 34);
    final r = RRect.fromRectAndRadius(rect, const Radius.circular(5));
    canvas.drawRRect(r, Paint()..color = const Color(0xFF100E0C));
    canvas.drawRRect(
      r,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.3
        ..color = active ? activeColor : const Color(0xFF4B4036),
    );
    if (active) {
      canvas.drawRRect(
        r,
        Paint()
          ..color = activeColor.withValues(alpha: .16)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8),
      );
    }
    _text(
      canvas,
      text,
      center,
      22,
      active ? activeColor : const Color(0xFF4A4037),
      FontWeight.w900,
    );
  }

  void _text(
    Canvas canvas,
    String text,
    Offset center,
    double fontSize,
    Color color,
    FontWeight weight,
  ) {
    final tp = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(
          color: color,
          fontSize: fontSize,
          fontWeight: weight,
          height: 1,
        ),
      ),
      textDirection: TextDirection.rtl,
      textAlign: TextAlign.center,
      maxLines: 1,
    )..layout();
    tp.paint(canvas, center - Offset(tp.width / 2, tp.height / 2));
  }

  @override
  bool shouldRepaint(covariant _IndustrialSwitchPainter oldDelegate) {
    return oldDelegate.progress != progress || oldDelegate.isOn != isOn;
  }
}

Future<void> _saveSessionAndOpen(
  BuildContext context,
  Map<String, dynamic> data,
) async {
  final token = '${data['token'] ?? ''}';
  if (token.isEmpty) throw Exception('لم يستلم التطبيق رمز الدخول من السيرفر');

  final prefs = await SharedPreferences.getInstance();
  await prefs.setString('token', token);
  await prefs.setString('full_name', '${data['full_name'] ?? ''}');
  await prefs.setString('employee_code', '${data['employee_code'] ?? ''}');
  if (data['role'] != null) await prefs.setString('role', '${data['role']}');

  api.token = token;
  if (!context.mounted) return;

  Navigator.pushAndRemoveUntil(
    context,
    MaterialPageRoute(
      builder: (_) => HomePage(
        fullName: '${data['full_name'] ?? ''}',
        employeeCode: '${data['employee_code'] ?? ''}',
        role: '${data['role'] ?? 'employee'}',
      ),
    ),
    (_) => false,
  );
}

class FirstLoginSetupPage extends StatefulWidget {
  final String employeeCode;
  final String currentPassword;

  const FirstLoginSetupPage({
    super.key,
    required this.employeeCode,
    required this.currentPassword,
  });

  @override
  State<FirstLoginSetupPage> createState() => _FirstLoginSetupPageState();
}

class _FirstLoginSetupPageState extends State<FirstLoginSetupPage> {
  late final TextEditingController oldPassword;
  final email = TextEditingController();
  final newPassword = TextEditingController();
  final confirmPassword = TextEditingController();
  bool loading = false;
  String? error;

  @override
  void initState() {
    super.initState();
    oldPassword = TextEditingController(text: widget.currentPassword);
  }

  Future<void> submit() async {
    FocusScope.of(context).unfocus();
    final oldPass = oldPassword.text;
    final mail = email.text.trim();
    final pass1 = newPassword.text;
    final pass2 = confirmPassword.text;

    if (oldPass.isEmpty || mail.isEmpty || pass1.isEmpty || pass2.isEmpty) {
      setState(() => error = 'من فضلك املأ كل الحقول');
      return;
    }
    if (!mail.contains('@')) {
      setState(() => error = 'من فضلك أدخل بريد إلكتروني صحيح');
      return;
    }
    if (pass1 != pass2) {
      setState(() => error = 'كلمتا المرور الجديدتان غير متطابقتين');
      return;
    }

    setState(() {
      loading = true;
      error = null;
    });

    try {
      final response = await api.post('/api/first-login-setup', {
        'employee_code': widget.employeeCode,
        'old_password': oldPass,
        'new_password': pass1,
        'email': mail,
      });
      final dynamic decoded = jsonDecode(response.body);
      final data = decoded is Map ? Map<String, dynamic>.from(decoded) : <String, dynamic>{};

      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw Exception(data['error'] ?? 'تعذر حفظ بيانات أول دخول');
      }
      if (!mounted) return;

      if (data['must_complete_profile'] == true) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => CompleteProfilePage(
              employeeCode: '${data['employee_code'] ?? widget.employeeCode}',
              currentPassword: pass1,
            ),
          ),
        );
        return;
      }

      await _saveSessionAndOpen(context, data);
    } catch (e) {
      if (mounted) setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  void dispose() {
    oldPassword.dispose();
    email.dispose();
    newPassword.dispose();
    confirmPassword.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return _AuthBackground(
      child: _AuthCard(
        title: 'إعداد أول دخول',
        subtitle: 'تأكيد الحساب وتغيير كلمة المرور',
        child: Column(
          children: [
            TextField(controller: oldPassword, obscureText: true, decoration: _authInputDecoration('كلمة المرور الحالية', Icons.lock_clock_outlined)),
            const SizedBox(height: 12),
            TextField(controller: email, keyboardType: TextInputType.emailAddress, decoration: _authInputDecoration('البريد الإلكتروني', Icons.email_outlined)),
            const SizedBox(height: 12),
            TextField(controller: newPassword, obscureText: true, decoration: _authInputDecoration('كلمة المرور الجديدة', Icons.lock_reset_outlined)),
            const SizedBox(height: 12),
            TextField(controller: confirmPassword, obscureText: true, onSubmitted: (_) => submit(), decoration: _authInputDecoration('تأكيد كلمة المرور الجديدة', Icons.verified_user_outlined)),
            if (error != null) ...[const SizedBox(height: 12), _InlineMessage(message: error!, isError: true)],
            const SizedBox(height: 18),
            _AuthSubmitButton(label: 'حفظ والدخول', loading: loading, onPressed: submit),
          ],
        ),
      ),
    );
  }
}

class CompleteProfilePage extends StatefulWidget {
  final String employeeCode;
  final String currentPassword;

  const CompleteProfilePage({
    super.key,
    required this.employeeCode,
    required this.currentPassword,
  });

  @override
  State<CompleteProfilePage> createState() => _CompleteProfilePageState();
}

class _CompleteProfilePageState extends State<CompleteProfilePage> {
  final phone = TextEditingController();
  final nationalId = TextEditingController();
  bool loading = false;
  String? error;

  Future<void> submit() async {
    FocusScope.of(context).unfocus();
    final phoneValue = phone.text.trim();
    final nationalValue = nationalId.text.trim();

    if (!RegExp(r'^\d{11}$').hasMatch(phoneValue)) {
      setState(() => error = 'رقم الهاتف لازم يكون 11 رقم بالظبط، أرقام فقط');
      return;
    }
    if (!RegExp(r'^\d{14}$').hasMatch(nationalValue)) {
      setState(() => error = 'الرقم القومي لازم يكون 14 رقم بالظبط، أرقام فقط');
      return;
    }

    setState(() {
      loading = true;
      error = null;
    });

    try {
      final response = await api.post('/api/complete-profile', {
        'employee_code': widget.employeeCode,
        'password': widget.currentPassword,
        'phone': phoneValue,
        'national_id': nationalValue,
      });
      final dynamic decoded = jsonDecode(response.body);
      final data = decoded is Map ? Map<String, dynamic>.from(decoded) : <String, dynamic>{};

      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw Exception(data['error'] ?? 'تعذر استكمال البيانات');
      }
      if (!mounted) return;
      await _saveSessionAndOpen(context, data);
    } catch (e) {
      if (mounted) setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  void dispose() {
    phone.dispose();
    nationalId.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return _AuthBackground(
      child: _AuthCard(
        title: 'استكمال بيانات الحساب',
        subtitle: 'البيانات المطلوبة لتأمين حسابك',
        child: Column(
          children: [
            TextField(controller: phone, keyboardType: TextInputType.phone, maxLength: 11, decoration: _authInputDecoration('رقم الهاتف', Icons.phone_android_outlined)),
            const SizedBox(height: 4),
            TextField(controller: nationalId, keyboardType: TextInputType.number, maxLength: 14, onSubmitted: (_) => submit(), decoration: _authInputDecoration('الرقم القومي', Icons.credit_card_outlined)),
            if (error != null) ...[const SizedBox(height: 8), _InlineMessage(message: error!, isError: true)],
            const SizedBox(height: 16),
            _AuthSubmitButton(label: 'حفظ والدخول', loading: loading, onPressed: submit),
          ],
        ),
      ),
    );
  }
}

class ForgotPasswordPage extends StatefulWidget {
  const ForgotPasswordPage({super.key});

  @override
  State<ForgotPasswordPage> createState() => _ForgotPasswordPageState();
}

class _ForgotPasswordPageState extends State<ForgotPasswordPage> {
  final employeeCode = TextEditingController();
  final email = TextEditingController();
  final verifyCode = TextEditingController();
  final newPassword = TextEditingController();
  final confirmPassword = TextEditingController();

  bool step2 = false;
  bool loading = false;
  String? error;
  String? success;

  Future<void> sendCode() async {
    final code = employeeCode.text.trim();
    final mail = email.text.trim();
    if (code.isEmpty || mail.isEmpty) {
      setState(() => error = 'من فضلك أدخل كود الموظف والبريد الإلكتروني');
      return;
    }

    setState(() {
      loading = true;
      error = null;
      success = null;
    });
    try {
      final response = await api.post('/api/forgot-password', {
        'employee_code': code,
        'email': mail,
      });
      final dynamic decoded = jsonDecode(response.body);
      final data = decoded is Map ? Map<String, dynamic>.from(decoded) : <String, dynamic>{};
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw Exception(data['error'] ?? 'تعذر إرسال كود التحقق');
      }
      if (mounted) setState(() => step2 = true);
    } catch (e) {
      if (mounted) setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> resetPassword() async {
    final verification = verifyCode.text.trim();
    final pass1 = newPassword.text;
    final pass2 = confirmPassword.text;

    if (verification.isEmpty || pass1.isEmpty || pass2.isEmpty) {
      setState(() => error = 'من فضلك املأ كل الحقول');
      return;
    }
    if (pass1 != pass2) {
      setState(() => error = 'كلمتا المرور غير متطابقتين');
      return;
    }

    setState(() {
      loading = true;
      error = null;
      success = null;
    });
    try {
      final response = await api.post('/api/reset-password', {
        'employee_code': employeeCode.text.trim(),
        'code': verification,
        'new_password': pass1,
      });
      final dynamic decoded = jsonDecode(response.body);
      final data = decoded is Map ? Map<String, dynamic>.from(decoded) : <String, dynamic>{};
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw Exception(data['error'] ?? 'تعذر تغيير كلمة المرور');
      }
      if (!mounted) return;
      setState(() => success = 'تم تغيير كلمة المرور بنجاح. يمكنك تسجيل الدخول الآن.');
      await Future<void>.delayed(const Duration(milliseconds: 500));
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  void dispose() {
    employeeCode.dispose();
    email.dispose();
    verifyCode.dispose();
    newPassword.dispose();
    confirmPassword.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return _AuthBackground(
      showBack: true,
      child: _AuthCard(
        title: 'نسيت كلمة المرور',
        subtitle: step2 ? 'أدخل كود التحقق وكلمة المرور الجديدة' : 'سنرسل كود تحقق إلى بريدك المسجل',
        child: Column(
          children: [
            if (!step2) ...[
              TextField(controller: employeeCode, keyboardType: TextInputType.number, decoration: _authInputDecoration('كود الموظف', Icons.badge_outlined)),
              const SizedBox(height: 12),
              TextField(controller: email, keyboardType: TextInputType.emailAddress, onSubmitted: (_) => sendCode(), decoration: _authInputDecoration('البريد الإلكتروني', Icons.email_outlined)),
            ] else ...[
              TextField(controller: verifyCode, keyboardType: TextInputType.number, decoration: _authInputDecoration('كود التحقق', Icons.pin_outlined)),
              const SizedBox(height: 12),
              TextField(controller: newPassword, obscureText: true, decoration: _authInputDecoration('كلمة المرور الجديدة', Icons.lock_reset_outlined)),
              const SizedBox(height: 12),
              TextField(controller: confirmPassword, obscureText: true, onSubmitted: (_) => resetPassword(), decoration: _authInputDecoration('تأكيد كلمة المرور', Icons.verified_user_outlined)),
            ],
            if (error != null) ...[const SizedBox(height: 12), _InlineMessage(message: error!, isError: true)],
            if (success != null) ...[const SizedBox(height: 12), _InlineMessage(message: success!, isError: false)],
            const SizedBox(height: 18),
            _AuthSubmitButton(
              label: step2 ? 'حفظ كلمة المرور الجديدة' : 'إرسال كود التحقق',
              loading: loading,
              onPressed: step2 ? resetPassword : sendCode,
            ),
            if (step2)
              TextButton(
                onPressed: loading ? null : () => setState(() => step2 = false),
                child: const Text('الرجوع وتعديل البيانات'),
              ),
          ],
        ),
      ),
    );
  }
}

class _AuthBackground extends StatelessWidget {
  final Widget child;
  final bool showBack;

  const _AuthBackground({required this.child, this.showBack = false});

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        body: Stack(
          fit: StackFit.expand,
          children: [
            Image.network(
              'https://commons.wikimedia.org/wiki/Special:FilePath/Transmission_tower_at_dusk_(Unsplash).jpg',
              fit: BoxFit.cover,
              errorBuilder: (_, __, ___) => Container(color: EmployeePortalApp.navy),
            ),
            Container(
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topRight,
                  end: Alignment.bottomLeft,
                  colors: [Color(0xF0460C16), Color(0xD95A1622), Color(0xB8782D37)],
                ),
              ),
            ),
            Positioned.fill(
              child: IgnorePointer(
                child: CustomPaint(painter: _EnergyLinePainter()),
              ),
            ),
            SafeArea(
              child: Stack(
                children: [
                  if (showBack)
                    Positioned(
                      top: 8,
                      right: 8,
                      child: IconButton.filledTonal(
                        onPressed: () => Navigator.maybePop(context),
                        icon: const Icon(Icons.arrow_forward),
                      ),
                    ),
                  Center(
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.all(24),
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 420),
                        child: child,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _AuthCard extends StatelessWidget {
  final String title;
  final String subtitle;
  final Widget child;

  const _AuthCard({required this.title, required this.subtitle, required this.child});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      clipBehavior: Clip.antiAlias,
      elevation: 18,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: Column(
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 22),
            decoration: const BoxDecoration(
              color: EmployeePortalApp.navyLight,
              border: Border(bottom: BorderSide(color: EmployeePortalApp.gold, width: 3)),
            ),
            child: Row(
              children: [
                Container(
                  width: 58,
                  height: 58,
                  decoration: const BoxDecoration(color: Colors.white, shape: BoxShape.circle),
                  child: const Icon(Icons.electric_bolt, color: EmployeePortalApp.navy, size: 34),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 18)),
                      const SizedBox(height: 3),
                      Text(subtitle, style: const TextStyle(color: EmployeePortalApp.goldSoft, fontSize: 13, fontWeight: FontWeight.w600)),
                    ],
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(26),
            child: child,
          ),
        ],
      ),
    );
  }
}

InputDecoration _authInputDecoration(String label, IconData icon) {
  return InputDecoration(
    labelText: label,
    prefixIcon: Icon(icon),
    filled: true,
    fillColor: Colors.white,
    border: OutlineInputBorder(borderRadius: BorderRadius.circular(6)),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(6),
      borderSide: const BorderSide(color: EmployeePortalApp.line, width: 1.5),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(6),
      borderSide: const BorderSide(color: EmployeePortalApp.gold, width: 1.7),
    ),
  );
}

class _AuthSubmitButton extends StatelessWidget {
  final String label;
  final bool loading;
  final VoidCallback onPressed;

  const _AuthSubmitButton({required this.label, required this.loading, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 50,
      child: FilledButton(
        style: FilledButton.styleFrom(
          backgroundColor: EmployeePortalApp.navy,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
        ),
        onPressed: loading ? null : onPressed,
        child: loading
            ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white))
            : Text(label, style: const TextStyle(fontWeight: FontWeight.w800)),
      ),
    );
  }
}

class _InlineMessage extends StatelessWidget {
  final String message;
  final bool isError;

  const _InlineMessage({required this.message, required this.isError});

  @override
  Widget build(BuildContext context) {
    final color = isError ? EmployeePortalApp.red : EmployeePortalApp.green;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(11),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        border: Border.all(color: color.withValues(alpha: 0.55)),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(message, style: TextStyle(color: color, fontSize: 13)),
    );
  }
}

class _EnergyLinePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = EmployeePortalApp.gold.withValues(alpha: 0.32)
      ..strokeWidth = 2;
    canvas.drawLine(Offset(0, size.height * .52), Offset(size.width, size.height * .52), paint);

    final dotPaint = Paint()..color = EmployeePortalApp.gold.withValues(alpha: .72);
    for (final p in [
      Offset(62, size.height * .12),
      Offset(size.width - 62, size.height * .12),
      Offset(62, size.height * .86),
      Offset(size.width - 62, size.height * .86),
    ]) {
      canvas.drawCircle(p, 4, dotPaint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}



class NotificationsPage extends StatefulWidget {
  const NotificationsPage({super.key});

  @override
  State<NotificationsPage> createState() => _NotificationsPageState();
}

class _NotificationsPageState extends State<NotificationsPage> {
  bool loading = true;
  String? error;
  List<Map<String, dynamic>> items = [];

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final response = await api.get('/api/announcements');
      final body = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(body is Map ? (body['error'] ?? 'تعذر تحميل الإشعارات') : 'تعذر تحميل الإشعارات');
      }
      final list = (body as List).whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
      setState(() => items = list);

      for (final a in list.where((e) => e['is_read'] != true)) {
        final id = a['id'];
        if (id != null) {
          api.post('/api/announcements/$id/read', {}).catchError((_) => http.Response('', 500));
        }
      }
      if (mounted) {
        setState(() {
          for (final a in items) {
            a['is_read'] = true;
          }
        });
      }
    } catch (e) {
      setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> toggleLike(Map<String, dynamic> a) async {
    final id = a['id'];
    if (id == null) return;
    try {
      final response = await api.post('/api/announcements/$id/like', {});
      final body = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(body['error'] ?? 'تعذر تسجيل الإعجاب');
      }
      setState(() {
        a['is_liked'] = body['is_liked'];
        a['like_count'] = body['like_count'];
      });
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(cleanError(e))),
      );
    }
  }

  void openAnnouncementAttachment(String fileName) {
    final token = api.token;
    if (token == null || token.isEmpty || fileName.trim().isEmpty) return;

    final safeFileName = Uri.encodeComponent(fileName.trim());
    final url =
        '$apiBaseUrl/uploads/$safeFileName?token=${Uri.encodeQueryComponent(token)}';

    launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    if (loading) return const Center(child: CircularProgressIndicator());
    if (error != null) return _ErrorView(message: error!, onRetry: load);

    return RefreshIndicator(
      onRefresh: load,
      child: items.isEmpty
          ? ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              children: const [
                SizedBox(height: 160),
                Center(child: Text('لا توجد إشعارات حتى الآن')),
              ],
            )
          : ListView.builder(
              padding: const EdgeInsets.all(14),
              itemCount: items.length,
              itemBuilder: (_, i) {
                final a = items[i];
                final liked = a['is_liked'] == true;
                return Card(
                  margin: const EdgeInsets.only(bottom: 12),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Icon(Icons.notifications_active_outlined,
                                color: EmployeePortalApp.navy),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                '${a['title'] ?? 'إشعار'}',
                                style: const TextStyle(
                                  fontWeight: FontWeight.w800,
                                  fontSize: 16,
                                  color: EmployeePortalApp.navy,
                                ),
                              ),
                            ),
                          ],
                        ),
                        if ('${a['created_at'] ?? ''}'.isNotEmpty) ...[
                          const SizedBox(height: 4),
                          Text('${a['created_at']}',
                              style: const TextStyle(color: Colors.grey, fontSize: 12)),
                        ],
                        if ('${a['body'] ?? ''}'.isNotEmpty) ...[
                          const SizedBox(height: 10),
                          Text('${a['body']}'),
                        ],
                        if ('${a['file_name'] ?? ''}'.isNotEmpty) ...[
                          const SizedBox(height: 10),
                          InkWell(
                            onTap: () => openAnnouncementAttachment(
                              (a['file_name'] ?? '').toString(),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Icon(
                                  Icons.attach_file,
                                  size: 18,
                                  color: EmployeePortalApp.navy,
                                ),
                                const SizedBox(width: 6),
                                Flexible(
                                  child: Text(
                                    'فتح المرفق: ${a['original_name'] ?? 'يوجد مرفق'}',
                                    style: const TextStyle(
                                      color: EmployeePortalApp.navy,
                                      fontWeight: FontWeight.w700,
                                      decoration: TextDecoration.underline,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                        const SizedBox(height: 10),
                        OutlinedButton.icon(
                          onPressed: () => toggleLike(a),
                          icon: Icon(liked ? Icons.thumb_up : Icons.thumb_up_outlined),
                          label: Text('إعجاب ${a['like_count'] ?? 0}'),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
    );
  }
}

class ContactPage extends StatefulWidget {
  const ContactPage({super.key});

  @override
  State<ContactPage> createState() => _ContactPageState();
}

class _ContactPageState extends State<ContactPage> {
  final message = TextEditingController();
  bool loading = true;
  bool sending = false;
  String? error;
  List<Map<String, dynamic>> messages = [];

  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    message.dispose();
    super.dispose();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final response = await api.get('/api/messages/my');
      final body = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(body is Map ? (body['error'] ?? 'تعذر تحميل الرسائل') : 'تعذر تحميل الرسائل');
      }
      final list = (body as List).whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
      setState(() => messages = list);

      for (final m in list.where((e) => e['admin_reply'] != null && e['employee_has_seen_reply'] != true)) {
        final id = m['id'];
        if (id != null) {
          api.post('/api/messages/$id/seen', {}).catchError((_) => http.Response('', 500));
        }
      }
    } catch (e) {
      setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> send() async {
    final text = message.text.trim();
    if (text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('من فضلك اكتب رسالة')),
      );
      return;
    }
    setState(() => sending = true);
    try {
      final response = await api.post('/api/messages', {'message': text});
      final body = jsonDecode(response.body);
      if (response.statusCode != 200 && response.statusCode != 201) {
        throw Exception(body['error'] ?? 'تعذر إرسال الرسالة');
      }
      message.clear();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('✓ ${body['message'] ?? 'تم إرسال الرسالة'}')),
      );
      await load();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(cleanError(e))),
      );
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  Future<void> toggleReplyLike(Map<String, dynamic> m) async {
    final id = m['id'];
    if (id == null) return;
    try {
      final response = await api.post('/api/messages/$id/like-reply', {});
      final body = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(body['error'] ?? 'تعذر تسجيل الإعجاب');
      }
      setState(() => m['reply_liked'] = body['reply_liked']);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(cleanError(e))));
    }
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: load,
      child: ListView(
        padding: const EdgeInsets.all(14),
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text(
                    '✉️ تواصل معنا',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                      color: EmployeePortalApp.navy,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'اكتب رسالتك أو مشكلتك وهتوصل مباشرة لمسؤول النظام مع اسمك وكودك تلقائيًا.',
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: message,
                    minLines: 4,
                    maxLines: 7,
                    decoration: const InputDecoration(
                      labelText: 'رسالتك',
                      border: OutlineInputBorder(),
                      alignLabelWithHint: true,
                    ),
                  ),
                  const SizedBox(height: 12),
                  FilledButton.icon(
                    onPressed: sending ? null : send,
                    icon: sending
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Icon(Icons.send),
                    label: const Text('إرسال'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 14),
          const Text(
            'رسائلك السابقة',
            style: TextStyle(
              fontWeight: FontWeight.w800,
              color: EmployeePortalApp.navy,
              fontSize: 16,
            ),
          ),
          const SizedBox(height: 8),
          if (loading)
            const Padding(
              padding: EdgeInsets.all(30),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (error != null)
            _ErrorView(message: error!, onRetry: load)
          else if (messages.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(20),
                child: Center(child: Text('لسه معملتش أي رسالة')),
              ),
            )
          else
            ...messages.map((m) {
              final hasReply = m['admin_reply'] != null && '${m['admin_reply']}'.isNotEmpty;
              final liked = m['reply_liked'] == true;
              return Card(
                margin: const EdgeInsets.only(bottom: 10),
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'رسالتك — ${m['created_at'] ?? ''}',
                        style: const TextStyle(color: Colors.grey, fontSize: 12),
                      ),
                      const SizedBox(height: 5),
                      Text('${m['message'] ?? ''}'),
                      const Divider(height: 22),
                      if (hasReply) ...[
                        Text(
                          'رد المسؤول — ${m['replied_at'] ?? ''}',
                          style: const TextStyle(
                            color: EmployeePortalApp.gold,
                            fontWeight: FontWeight.w800,
                            fontSize: 12,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: EmployeePortalApp.goldSoft,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text('${m['admin_reply']}'),
                        ),
                        const SizedBox(height: 6),
                        OutlinedButton.icon(
                          onPressed: () => toggleReplyLike(m),
                          icon: Icon(liked ? Icons.thumb_up : Icons.thumb_up_outlined),
                          label: Text(liked ? 'شكرًا' : 'أعجبني'),
                        ),
                      ] else
                        const Text('⏳ لسه منتظر رد', style: TextStyle(color: Colors.grey)),
                    ],
                  ),
                ),
              );
            }),
        ],
      ),
    );
  }
}


class RatingPage extends StatefulWidget {
  const RatingPage({super.key});

  @override
  State<RatingPage> createState() => _RatingPageState();
}

class _RatingPageState extends State<RatingPage> {
  int rating = 0;
  bool sending = false;
  final comment = TextEditingController();

  @override
  void dispose() {
    comment.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (rating < 1) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('اختار عدد النجوم الأول')),
      );
      return;
    }

    setState(() => sending = true);
    try {
      final response = await api.post('/api/service-rating', {
        'rating': rating,
        'comment': comment.text.trim(),
      });
      final body = jsonDecode(response.body);
      if (response.statusCode != 200 && response.statusCode != 201) {
        throw Exception(body is Map ? (body['error'] ?? 'تعذر إرسال التقييم') : 'تعذر إرسال التقييم');
      }

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('✓ ${body['message'] ?? 'تم إرسال التقييم'}')),
      );
      comment.clear();
      setState(() => rating = 0);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(cleanError(e))),
      );
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                const Icon(Icons.star_rate_rounded,
                    size: 52, color: EmployeePortalApp.gold),
                const SizedBox(height: 10),
                const Text(
                  'تقييم الخدمة',
                  style: TextStyle(
                    fontSize: 21,
                    fontWeight: FontWeight.w800,
                    color: EmployeePortalApp.navy,
                  ),
                ),
                const SizedBox(height: 6),
                const Text(
                  'رأيك يهمنا لتحسين الخدمة باستمرار.',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 20),
                Wrap(
                  alignment: WrapAlignment.center,
                  children: List.generate(5, (i) {
                    final n = i + 1;
                    return IconButton(
                      tooltip: '$n',
                      onPressed: () => setState(() => rating = n),
                      iconSize: 42,
                      icon: Icon(
                        n <= rating ? Icons.star : Icons.star_border,
                        color: EmployeePortalApp.gold,
                      ),
                    );
                  }),
                ),
                const SizedBox(height: 8),
                Text(
                  rating == 0 ? 'اختر من 1 إلى 5 نجوم' : 'تقييمك: $rating من 5',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 20),
                TextField(
                  controller: comment,
                  minLines: 3,
                  maxLines: 5,
                  decoration: const InputDecoration(
                    labelText: 'تعليق (اختياري)',
                    border: OutlineInputBorder(),
                    alignLabelWithHint: true,
                  ),
                ),
                const SizedBox(height: 14),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: sending ? null : submit,
                    icon: sending
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.send),
                    label: const Text('إرسال التقييم'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}


class ChangePasswordPage extends StatefulWidget {
  const ChangePasswordPage({super.key});

  @override
  State<ChangePasswordPage> createState() => _ChangePasswordPageState();
}

class _ChangePasswordPageState extends State<ChangePasswordPage> {
  final oldPassword = TextEditingController();
  final newPassword = TextEditingController();
  final confirmPassword = TextEditingController();

  bool sending = false;
  bool showOld = false;
  bool showNew = false;
  bool showConfirm = false;

  @override
  void dispose() {
    oldPassword.dispose();
    newPassword.dispose();
    confirmPassword.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    final oldPass = oldPassword.text;
    final newPass = newPassword.text;
    final confirmPass = confirmPassword.text;

    if (oldPass.isEmpty || newPass.isEmpty || confirmPass.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('من فضلك املأ كل الحقول')),
      );
      return;
    }

    if (newPass != confirmPass) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('كلمتا المرور الجديدتان غير متطابقتين')),
      );
      return;
    }

    setState(() => sending = true);

    try {
      final response = await api.post('/api/change-password', {
        'old_password': oldPass,
        'new_password': newPass,
      });

      final body = jsonDecode(response.body);

      if (response.statusCode != 200 && response.statusCode != 201) {
        throw Exception(
          body is Map
              ? (body['error'] ?? 'تعذر تغيير كلمة المرور')
              : 'تعذر تغيير كلمة المرور',
        );
      }

      if (!mounted) return;

      oldPassword.clear();
      newPassword.clear();
      confirmPassword.clear();

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('✓ ${body['message'] ?? 'تم تغيير كلمة المرور بنجاح'}'),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(cleanError(e))),
      );
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  InputDecoration passwordDecoration({
    required String label,
    required bool visible,
    required VoidCallback onToggle,
  }) {
    return InputDecoration(
      labelText: label,
      border: const OutlineInputBorder(),
      suffixIcon: IconButton(
        tooltip: visible ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور',
        onPressed: onToggle,
        icon: Icon(
          visible ? Icons.visibility_off : Icons.visibility,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                const Icon(
                  Icons.lock_reset_rounded,
                  size: 52,
                  color: EmployeePortalApp.gold,
                ),
                const SizedBox(height: 10),
                const Text(
                  'تغيير كلمة المرور',
                  style: TextStyle(
                    fontSize: 21,
                    fontWeight: FontWeight.w800,
                    color: EmployeePortalApp.navy,
                  ),
                ),
                const SizedBox(height: 20),
                TextField(
                  controller: oldPassword,
                  obscureText: !showOld,
                  textInputAction: TextInputAction.next,
                  decoration: passwordDecoration(
                    label: 'كلمة المرور الحالية',
                    visible: showOld,
                    onToggle: () => setState(() => showOld = !showOld),
                  ),
                ),
                const SizedBox(height: 14),
                TextField(
                  controller: newPassword,
                  obscureText: !showNew,
                  textInputAction: TextInputAction.next,
                  decoration: passwordDecoration(
                    label: 'كلمة المرور الجديدة',
                    visible: showNew,
                    onToggle: () => setState(() => showNew = !showNew),
                  ),
                ),
                const SizedBox(height: 14),
                TextField(
                  controller: confirmPassword,
                  obscureText: !showConfirm,
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) {
                    if (!sending) submit();
                  },
                  decoration: passwordDecoration(
                    label: 'تأكيد كلمة المرور الجديدة',
                    visible: showConfirm,
                    onToggle: () => setState(() => showConfirm = !showConfirm),
                  ),
                ),
                const SizedBox(height: 18),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: sending ? null : submit,
                    icon: sending
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.save),
                    label: Text(
                      sending
                          ? 'جاري الحفظ...'
                          : 'حفظ كلمة المرور الجديدة',
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class HomePage extends StatefulWidget {
  final String fullName;
  final String employeeCode;
  final String role;

  const HomePage({
    super.key,
    required this.fullName,
    required this.employeeCode,
    required this.role,
  });

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int index = 0;

  bool get isAdmin => widget.role == 'hr_admin';

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
    api.token = null;
    if (!mounted) return;
    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (_) => const LoginPage()),
      (_) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final titles = <String>[
      'الرئيسية',
      'بياناتي الإدارية',
      'شريط المرتب',
      'سجل الأجور',
      'الإشعارات',
      'تواصل معنا',
      'تقييم الخدمة',
      'تغيير كلمة المرور',
      if (isAdmin) 'لوحة الإدارة',
    ];

    final pages = <Widget>[
      DashboardPage(
        fullName: widget.fullName,
        employeeCode: widget.employeeCode,
        isAdmin: isAdmin,
        onPayslip: () => setState(() => index = 2),
        onWageRecord: () => setState(() => index = 3),
        onAdminInfo: () => setState(() => index = 1),
        onNotifications: () => setState(() => index = 4),
        onAdminPanel: isAdmin ? () => setState(() => index = 8) : null,
      ),
      const AdminInfoPage(),
      const PayslipPage(),
      const WageRecordPage(),
      const NotificationsPage(),
      const ContactPage(),
      const RatingPage(),
      const ChangePasswordPage(),
      if (isAdmin) const AdminDashboardPage(),
    ];

    if (index >= pages.length) index = 0;

    return Directionality(
      textDirection: TextDirection.rtl,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final desktop = constraints.maxWidth >= 980;
          if (!desktop) {
            return _mobileShell(titles, pages);
          }
          return Scaffold(
            backgroundColor: const Color(0xFFF8F2E9),
            body: Column(
              children: [
                _DesktopTopBar(
                  title: titles[index],
                  fullName: widget.fullName,
                  employeeCode: widget.employeeCode,
                  onLogout: logout,
                ),
                Expanded(
                  child: Row(
                    children: [
                      _DesktopSideBar(
                        selectedIndex: index,
                        isAdmin: isAdmin,
                        onSelect: (i) => setState(() => index = i),
                        onLogout: logout,
                      ),
                      Expanded(
                        child: Container(
                          decoration: const BoxDecoration(
                            gradient: LinearGradient(
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                              colors: [
                                Color(0xFFFFFDF8),
                                Color(0xFFF8F2E9),
                                Color(0xFFF4EBDD),
                              ],
                            ),
                          ),
                          child: pages[index],
                        ),
                      ),
                    ],
                  ),
                ),
                const _PortalFooter(),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _mobileShell(List<String> titles, List<Widget> pages) {
    final destinations = <NavigationDestination>[
      const NavigationDestination(icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home), label: 'الرئيسية'),
      const NavigationDestination(icon: Icon(Icons.person_outline), selectedIcon: Icon(Icons.person), label: 'بياناتي'),
      const NavigationDestination(icon: Icon(Icons.receipt_long_outlined), selectedIcon: Icon(Icons.receipt_long), label: 'المرتب'),
      const NavigationDestination(icon: Icon(Icons.payments_outlined), selectedIcon: Icon(Icons.payments), label: 'الأجور'),
      const NavigationDestination(icon: Icon(Icons.notifications_none), selectedIcon: Icon(Icons.notifications), label: 'الإشعارات'),
      const NavigationDestination(icon: Icon(Icons.mail_outline), selectedIcon: Icon(Icons.mail), label: 'تواصل'),
      const NavigationDestination(icon: Icon(Icons.star_border), selectedIcon: Icon(Icons.star), label: 'تقييم'),
      const NavigationDestination(icon: Icon(Icons.lock_outline), selectedIcon: Icon(Icons.lock), label: 'كلمة المرور'),
      if (isAdmin) const NavigationDestination(icon: Icon(Icons.admin_panel_settings_outlined), selectedIcon: Icon(Icons.admin_panel_settings), label: 'الإدارة'),
    ];
    return Scaffold(
      appBar: AppBar(
        title: Text(titles[index]),
        actions: [IconButton(onPressed: logout, icon: const Icon(Icons.logout_rounded))],
      ),
      body: pages[index],
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (i) => setState(() => index = i),
        destinations: destinations,
      ),
    );
  }
}

class _DesktopTopBar extends StatelessWidget {
  final String title;
  final String fullName;
  final String employeeCode;
  final VoidCallback onLogout;

  const _DesktopTopBar({
    required this.title,
    required this.fullName,
    required this.employeeCode,
    required this.onLogout,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 72,
      padding: const EdgeInsets.symmetric(horizontal: 22),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [Color(0xFF6B1023), Color(0xFF8C142D), Color(0xFF6B1023)],
        ),
        boxShadow: [BoxShadow(color: Color(0x33000000), blurRadius: 10, offset: Offset(0, 3))],
      ),
      child: Row(
        children: [
          const Icon(Icons.menu_rounded, color: Colors.white, size: 28),
          const SizedBox(width: 18),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Text('بوابة الموظفين', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: 18)),
                const SizedBox(height: 2),
                const Text('الشركة المصرية لنقل الكهرباء - منطقة الدلتا', style: TextStyle(color: EmployeePortalApp.goldSoft, fontSize: 10.5, fontWeight: FontWeight.w700)),
              ],
            ),
          ),
          const Icon(Icons.notifications_none_rounded, color: Colors.white, size: 25),
          const SizedBox(width: 18),
          const _EmployeeProfileAvatar(size: 42),
          const SizedBox(width: 10),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 230),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(fullName, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: 13)),
                Text('كود العامل: $employeeCode', style: const TextStyle(color: EmployeePortalApp.goldSoft, fontSize: 10.5)),
              ],
            ),
          ),
          const SizedBox(width: 8),
          IconButton(tooltip: 'تسجيل الخروج', onPressed: onLogout, icon: const Icon(Icons.logout_rounded, color: Colors.white)),
        ],
      ),
    );
  }
}

class _DesktopSideBar extends StatelessWidget {
  final int selectedIndex;
  final bool isAdmin;
  final ValueChanged<int> onSelect;
  final VoidCallback onLogout;

  const _DesktopSideBar({
    required this.selectedIndex,
    required this.isAdmin,
    required this.onSelect,
    required this.onLogout,
  });

  @override
  Widget build(BuildContext context) {
    final items = <(IconData, String)>[
      (Icons.home_rounded, 'الرئيسية'),
      (Icons.person_outline_rounded, 'بياناتي الإدارية'),
      (Icons.receipt_long_outlined, 'شريط المرتب'),
      (Icons.account_balance_wallet_outlined, 'سجل الأجور'),
      (Icons.notifications_none_rounded, 'الإشعارات'),
      (Icons.forum_outlined, 'تواصل معنا'),
      (Icons.star_border_rounded, 'تقييم الخدمة'),
      (Icons.lock_outline_rounded, 'تغيير كلمة المرور'),
      if (isAdmin) (Icons.admin_panel_settings_outlined, 'لوحة الإدارة'),
    ];
    return Container(
      width: 238,
      color: const Color(0xFFFFFCF7),
      child: Column(
        children: [
          const SizedBox(height: 18),
          ...List.generate(items.length, (i) {
            final selected = selectedIndex == i;
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
              child: Material(
                color: selected ? const Color(0xFF7B1227) : Colors.transparent,
                borderRadius: BorderRadius.circular(10),
                child: InkWell(
                  borderRadius: BorderRadius.circular(10),
                  onTap: () => onSelect(i),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    child: Row(
                      children: [
                        Icon(items[i].$1, color: selected ? Colors.white : EmployeePortalApp.navy, size: 21),
                        const SizedBox(width: 12),
                        Expanded(child: Text(items[i].$2, style: TextStyle(color: selected ? Colors.white : const Color(0xFF5F4A45), fontWeight: selected ? FontWeight.w900 : FontWeight.w700, fontSize: 13))),
                      ],
                    ),
                  ),
                ),
              ),
            );
          }),
          const Spacer(),
          const Divider(height: 1),
          ListTile(
            onTap: onLogout,
            leading: const Icon(Icons.logout_rounded, color: EmployeePortalApp.navy),
            title: const Text('تسجيل خروج', style: TextStyle(color: EmployeePortalApp.navy, fontWeight: FontWeight.w900)),
          ),
          const SizedBox(height: 8),
        ],
      ),
    );
  }
}


class _PortalFooter extends StatelessWidget {
  const _PortalFooter();

  Future<void> _open(String url) async {
    await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
  }

  void _about(BuildContext context) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('حول النظام'),
        content: const Text(
          'Payroll Portal — بوابة الموظفين\n\n'
          'تم تصميم وتطوير وبرمجة هذا النظام بالكامل بواسطة خالد يوسف المنسي.\n'
          'Version 1.0.0\n'
          'تاريخ الإنشاء: يوليو 2026',
        ),
        actions: [
          FilledButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('إغلاق'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 64),
      padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 10),
      decoration: const BoxDecoration(
        color: Color(0xFFFFFCF7),
        border: Border(top: BorderSide(color: Color(0x33C9A24B))),
      ),
      child: Wrap(
        alignment: WrapAlignment.center,
        crossAxisAlignment: WrapCrossAlignment.center,
        spacing: 14,
        runSpacing: 6,
        children: [
          const Text(
            'تم تصميم وتطوير وبرمجة هذا النظام بالكامل بواسطة خالد يوسف المنسي',
            style: TextStyle(
              color: EmployeePortalApp.navy,
              fontWeight: FontWeight.w900,
              fontSize: 11.5,
            ),
          ),
          InkWell(
            onTap: () => _open('https://wa.me/201201413051'),
            child: const Text(
              'واتساب: 01201413051',
              style: TextStyle(
                color: Color(0xFFB16F00),
                fontWeight: FontWeight.w900,
                fontSize: 11.5,
              ),
            ),
          ),
          const Text('| Version 1.0.0 | © 2026 جميع الحقوق محفوظة |',
              style: TextStyle(color: Color(0xFF6A5B54), fontSize: 11)),
          TextButton.icon(
            onPressed: () => _about(context),
            icon: const Icon(Icons.info_outline, size: 18),
            label: const Text('حول النظام'),
          ),
          IconButton(
            tooltip: 'صفحة الشركة المصرية لنقل الكهرباء',
            onPressed: () => _open('https://www.facebook.com/EgyptEETC/'),
            icon: const Icon(Icons.facebook, color: Color(0xFF1877F2)),
          ),
          IconButton(
            tooltip: 'المنظومة الإلكترونية الموحدة - منطقة الدلتا',
            onPressed: () => _open('https://www.facebook.com/share/g/1EVn6FzQuq/'),
            icon: const Icon(Icons.facebook, color: Color(0xFF1877F2)),
          ),
        ],
      ),
    );
  }
}

class _EmployeeProfileAvatar extends StatefulWidget {
  final double size;
  const _EmployeeProfileAvatar({required this.size});

  @override
  State<_EmployeeProfileAvatar> createState() => _EmployeeProfileAvatarState();
}

class _EmployeeProfileAvatarState extends State<_EmployeeProfileAvatar> {
  String? photoUrl;

  @override
  void initState() {
    super.initState();
    profilePhotoRevision.addListener(_reload);
    _load();
  }

  @override
  void dispose() {
    profilePhotoRevision.removeListener(_reload);
    super.dispose();
  }

  void _reload() => _load();

  Future<void> _load() async {
    try {
      final r = await api.get('/api/employee/me');
      if (r.statusCode != 200) return;
      final body = jsonDecode(r.body);
      if (body is Map && body['photo_url'] != null && api.token != null) {
        final raw = '${body['photo_url']}';
        final url = raw.startsWith('http') ? raw : '$apiBaseUrl$raw';
        if (mounted) {
          setState(() {
            photoUrl = '$url?token=${Uri.encodeQueryComponent(api.token!)}&v=${profilePhotoRevision.value}';
          });
        }
      } else if (mounted) {
        setState(() => photoUrl = null);
      }
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final fallback = _ExactCompanyLogo(size: widget.size);
    if (photoUrl == null) return fallback;
    return ClipOval(
      child: Image.network(
        photoUrl!,
        width: widget.size,
        height: widget.size,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => fallback,
      ),
    );
  }
}

class DashboardPage extends StatefulWidget {
  final String fullName;
  final String employeeCode;
  final bool isAdmin;
  final VoidCallback onPayslip;
  final VoidCallback onWageRecord;
  final VoidCallback onAdminInfo;
  final VoidCallback onNotifications;
  final VoidCallback? onAdminPanel;

  const DashboardPage({
    super.key,
    required this.fullName,
    required this.employeeCode,
    required this.isAdmin,
    required this.onPayslip,
    required this.onWageRecord,
    required this.onAdminInfo,
    required this.onNotifications,
    this.onAdminPanel,
  });

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  Map<String, dynamic>? info;

  @override
  void initState() {
    super.initState();
    _loadInfo();
  }

  Future<void> _loadInfo() async {
    try {
      final r = await api.get('/api/employee/me');
      if (r.statusCode == 200 && mounted) {
        final body = jsonDecode(r.body);
        if (body is Map<String, dynamic>) setState(() => info = body);
      }
    } catch (_) {}
  }

  void _open(BuildContext context, Widget page) {
    Navigator.push(context, MaterialPageRoute(builder: (_) => page));
  }

  String _statusText() {
    final s = '${info?['status'] ?? ''}'.toLowerCase();
    return (s == 'active' || s == 'ساري' || s == '0') ? 'ساري' : (s.isEmpty ? 'ساري' : '${info?['status']}');
  }

  String _department() => '${info?['department'] ?? info?['department_name'] ?? 'الإدارة'}';
  String _hireDate() => '${info?['hire_date'] ?? '—'}';

  @override
  Widget build(BuildContext context) {
    final services = <_BoltService>[
      _BoltService(Icons.badge_rounded, 'بياناتي الإدارية', widget.onAdminInfo),
      _BoltService(Icons.receipt_long_rounded, 'شريط المرتب', widget.onPayslip),
      _BoltService(Icons.account_balance_wallet_rounded, 'سجل الأجور', widget.onWageRecord),
      _BoltService(Icons.notifications_active_rounded, 'الإشعارات', widget.onNotifications),
      _BoltService(Icons.forum_rounded, 'التواصل', () => _open(context, const ContactPage())),
      _BoltService(Icons.star_rounded, 'تقييم الخدمة', () => _open(context, const RatingPage())),
      _BoltService(Icons.lock_reset_rounded, 'كلمة المرور', () => _open(context, const ChangePasswordPage())),
      if (widget.isAdmin && widget.onAdminPanel != null) _BoltService(Icons.admin_panel_settings_rounded, 'الإدارة', widget.onAdminPanel!),
    ];

    return LayoutBuilder(
      builder: (context, constraints) {
        final desktop = constraints.maxWidth >= 900;
        return ListView(
          padding: EdgeInsets.symmetric(horizontal: desktop ? 32 : 12, vertical: 22),
          children: [
            Text('مرحباً بك، ${widget.fullName}', textAlign: TextAlign.right, style: const TextStyle(color: EmployeePortalApp.navy, fontSize: 21, fontWeight: FontWeight.w900)),
            const SizedBox(height: 4),
            Text('كود العامل: ${widget.employeeCode}', textAlign: TextAlign.right, style: const TextStyle(color: Color(0xFF6F5A50), fontSize: 13, fontWeight: FontWeight.w700)),
            const SizedBox(height: 18),
            Wrap(
              spacing: 14,
              runSpacing: 14,
              alignment: WrapAlignment.start,
              children: [
                _SummaryCard(icon: Icons.fact_check_outlined, title: 'آخر تحديث', value: _hireDate(), valueColor: EmployeePortalApp.navy),
                _SummaryCard(icon: Icons.account_tree_outlined, title: 'الإدارة', value: _department(), valueColor: EmployeePortalApp.navy),
                const _SummaryCard(icon: Icons.calendar_month_outlined, title: 'سنوات الخدمة', value: '—', valueColor: EmployeePortalApp.navy),
                _SummaryCard(icon: Icons.person_rounded, title: 'الحالة الوظيفية', value: _statusText(), valueColor: EmployeePortalApp.green),
              ],
            ),
            const SizedBox(height: 24),
            Row(
              children: [
                const Expanded(child: Divider(color: Color(0x55C9A24B))),
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 16),
                  child: Text('الخدمات المتاحة', style: TextStyle(color: Color(0xFFB16F00), fontSize: 18, fontWeight: FontWeight.w900)),
                ),
                const Expanded(child: Divider(color: Color(0x55C9A24B))),
              ],
            ),
            const SizedBox(height: 8),
            Center(
              child: SizedBox(
                width: 620,
                height: widget.isAdmin ? 530 : 470,
                child: Stack(
                  clipBehavior: Clip.none,
                  children: [
                    Center(child: Icon(Icons.bolt_rounded, size: 300, color: EmployeePortalApp.gold.withValues(alpha: .72))),
                    ..._servicePositions(services.length).asMap().entries.map((e) {
                      final i = e.key;
                      final p = e.value;
                      return Positioned(left: p.dx, top: p.dy, child: _CircularServiceButton(service: services[i]));
                    }),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }

  List<Offset> _servicePositions(int n) {
    final base = <Offset>[
      const Offset(260, 10),
      const Offset(90, 120),
      const Offset(430, 120),
      const Offset(260, 125),
      const Offset(260, 245),
      const Offset(120, 300),
      const Offset(400, 300),
      const Offset(260, 365),
    ];
    return base.take(n).toList();
  }
}

class _SummaryCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String value;
  final Color valueColor;
  const _SummaryCard({required this.icon, required this.title, required this.value, required this.valueColor});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 190,
      height: 108,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFDF8),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0x22C9A24B)),
        boxShadow: const [BoxShadow(color: Color(0x18000000), blurRadius: 12, offset: Offset(0, 5))],
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: const Color(0xFFB77805), size: 27),
          const SizedBox(height: 5),
          Text(title, style: const TextStyle(color: Color(0xFF67544D), fontSize: 11.5, fontWeight: FontWeight.w700)),
          const SizedBox(height: 3),
          Text(value, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(color: valueColor, fontSize: 13.5, fontWeight: FontWeight.w900)),
        ],
      ),
    );
  }
}

class _BoltService {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _BoltService(this.icon, this.label, this.onTap);
}

class _CircularServiceButton extends StatelessWidget {
  final _BoltService service;

  const _CircularServiceButton({required this.service});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 104,
      height: 104,
      child: Column(
        children: [
          Material(
            color: Colors.transparent,
            shape: const CircleBorder(),
            child: InkWell(
              customBorder: const CircleBorder(),
              onTap: service.onTap,
              child: Ink(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: const Color(0xFFFFFDF8),
                  border: Border.all(
                    color: EmployeePortalApp.gold,
                    width: 1.8,
                  ),
                  boxShadow: const [
                    BoxShadow(
                      color: Color(0x22C9A24B),
                      blurRadius: 12,
                      spreadRadius: 1,
                    ),
                    BoxShadow(
                      color: Color(0x225C1524),
                      blurRadius: 10,
                      offset: Offset(0, 5),
                    ),
                  ],
                ),
                child: Icon(
                  service.icon,
                  color: EmployeePortalApp.navy,
                  size: 31,
                ),
              ),
            ),
          ),
          const SizedBox(height: 5),
          SizedBox(
            width: 104,
            child: Text(
              service.label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: EmployeePortalApp.navy,
                fontSize: 11.5,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _BoltGlowPainter extends CustomPainter {
  final List<Offset> positions;

  const _BoltGlowPainter({required this.positions});

  @override
  void paint(Canvas canvas, Size size) {
    if (positions.length < 2) return;

    final points = positions
        .map(
          (p) => Offset(
            (size.width - 104) * p.dx + 36,
            (size.height - 104) * p.dy + 36,
          ),
        )
        .toList();

    final glowPath = Path()
      ..moveTo(points.first.dx, points.first.dy);

    for (final p in points.skip(1)) {
      glowPath.lineTo(p.dx, p.dy);
    }

    canvas.drawPath(
      glowPath,
      Paint()
        ..color = const Color(0x24C9A24B)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 13
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );

    canvas.drawPath(
      glowPath,
      Paint()
        ..color = const Color(0xA6C9A24B)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.2
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );
  }

  @override
  bool shouldRepaint(covariant _BoltGlowPainter oldDelegate) =>
      oldDelegate.positions != positions;
}

class _QuickCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _QuickCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      color: const Color(0xFFFFF4DF),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        onTap: onTap,
        leading: Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: EmployeePortalApp.navy,
            borderRadius: BorderRadius.circular(14),
            boxShadow: const [
              BoxShadow(
                color: Color(0x33C9A24B),
                blurRadius: 10,
                offset: Offset(0, 4),
              ),
            ],
          ),
          child: Icon(icon, color: EmployeePortalApp.gold),
        ),
        title: Text(
          title,
          style: const TextStyle(
            color: EmployeePortalApp.navy,
            fontWeight: FontWeight.w900,
          ),
        ),
        subtitle: Text(
          subtitle,
          style: const TextStyle(color: Color(0xFF6F5A50)),
        ),
        trailing: const Icon(
          Icons.arrow_back_ios_new_rounded,
          size: 17,
          color: EmployeePortalApp.navy,
        ),
      ),
    );
  }
}


class AdminInfoPage extends StatefulWidget {
  const AdminInfoPage({super.key});

  @override
  State<AdminInfoPage> createState() => _AdminInfoPageState();
}

class _AdminInfoPageState extends State<AdminInfoPage> {
  Map<String, dynamic>? data;
  String? error;
  bool loading = true;
  bool uploading = false;
  String? photoUrl;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });

    try {
      final response = await api.get('/api/employee/me');
      final body = jsonDecode(response.body);

      if (response.statusCode != 200) {
        throw Exception(body['error'] ?? 'تعذر تحميل البيانات');
      }

      if (!mounted) return;
      setState(() {
        data = Map<String, dynamic>.from(body);
        final raw = data!['photo_url'];
        if (raw != null && api.token != null) {
          final u = '$raw'.startsWith('http') ? '$raw' : '$apiBaseUrl$raw';
          photoUrl = '$u?token=${Uri.encodeQueryComponent(api.token!)}&v=${DateTime.now().millisecondsSinceEpoch}';
        } else {
          photoUrl = null;
        }
      });
    } on TimeoutException {
      if (mounted) {
        setState(() {
          error = 'السيرفر لم يستجب خلال 25 ثانية. جرّب مرة أخرى وتأكد أن ngrok والسيرفر يعملان.';
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> uploadPhoto() async {
    final picked = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['jpg', 'jpeg', 'png'],
      withData: true,
    );
    if (picked == null || picked.files.isEmpty) return;

    final file = picked.files.single;
    if (file.bytes == null) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('تعذر قراءة الصورة المختارة')),
        );
      }
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('حجم الصورة يجب ألا يزيد عن 2MB')),
        );
      }
      return;
    }

    setState(() => uploading = true);
    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$apiBaseUrl/api/employee/photo'),
      );
      request.headers['ngrok-skip-browser-warning'] = 'true';
      if (api.token != null) {
        request.headers['Authorization'] = 'Bearer ${api.token}';
      }
      request.files.add(
        http.MultipartFile.fromBytes(
          'photo',
          file.bytes!,
          filename: file.name,
        ),
      );

      final streamed = await request.send().timeout(const Duration(seconds: 35));
      final response = await http.Response.fromStream(streamed);
      final body = jsonDecode(response.body);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw Exception(body is Map ? (body['error'] ?? 'تعذر رفع الصورة') : 'تعذر رفع الصورة');
      }

      profilePhotoRevision.value++;
      await load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('✓ تم رفع الصورة بنجاح')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(cleanError(e))),
        );
      }
    } finally {
      if (mounted) setState(() => uploading = false);
    }
  }

  Widget _fieldRow(String label, dynamic value, {Color? valueColor}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: Color(0xFFE9E0D4))),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 145,
            child: Text(
              label,
              style: const TextStyle(
                color: Color(0xFF765F56),
                fontSize: 12,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          Expanded(
            child: Text(
              '${value ?? 'غير مسجل'}',
              style: TextStyle(
                color: valueColor ?? const Color(0xFF2E2724),
                fontSize: 13,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _profileCard() {
    final status = '${data?['status'] ?? ''}'.toLowerCase();
    final active = status == 'active' || status == '0' || status == 'ساري';
    final fallback = const _ExactCompanyLogo(size: 118);

    return Container(
      width: 230,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFDF8),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0x22C9A24B)),
        boxShadow: const [
          BoxShadow(color: Color(0x18000000), blurRadius: 14, offset: Offset(0, 6)),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ClipOval(
            child: photoUrl == null
                ? fallback
                : Image.network(
                    photoUrl!,
                    width: 118,
                    height: 118,
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => fallback,
                  ),
          ),
          const SizedBox(height: 12),
          Text(
            '${data?['full_name'] ?? ''}',
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: EmployeePortalApp.navy,
              fontWeight: FontWeight.w900,
              fontSize: 16,
            ),
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: uploading ? null : uploadPhoto,
            icon: uploading
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : const Icon(Icons.photo_camera_outlined),
            label: Text(uploading ? 'جارٍ الرفع...' : 'رفع صورتي'),
            style: FilledButton.styleFrom(
              backgroundColor: EmployeePortalApp.navy,
              foregroundColor: Colors.white,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'JPG, PNG — الحد الأقصى 2MB',
            textAlign: TextAlign.center,
            style: TextStyle(color: EmployeePortalApp.gray, fontSize: 10),
          ),
          const Divider(height: 28),
          const Text(
            'كود العامل',
            style: TextStyle(color: EmployeePortalApp.gray, fontSize: 11),
          ),
          Text(
            '${data?['employee_code'] ?? ''}',
            style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 15),
          ),
          const SizedBox(height: 10),
          const Text(
            'الحالة الوظيفية',
            style: TextStyle(color: EmployeePortalApp.gray, fontSize: 11),
          ),
          Text(
            active ? 'ساري' : '${data?['status'] ?? 'غير متاح'}',
            style: TextStyle(
              color: active ? EmployeePortalApp.green : EmployeePortalApp.red,
              fontWeight: FontWeight.w900,
              fontSize: 15,
            ),
          ),
        ],
      ),
    );
  }

  Widget _detailsCard() {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFFFFFDF8),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0x22C9A24B)),
        boxShadow: const [
          BoxShadow(color: Color(0x16000000), blurRadius: 14, offset: Offset(0, 6)),
        ],
      ),
      child: Column(
        children: [
          const Padding(
            padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Align(
              alignment: Alignment.centerRight,
              child: Text(
                'البيانات الأساسية',
                style: TextStyle(
                  color: EmployeePortalApp.navy,
                  fontWeight: FontWeight.w900,
                  fontSize: 15,
                ),
              ),
            ),
          ),
          _fieldRow('الاسم', data?['full_name']),
          _fieldRow('الرقم القومي', data?['national_id'] ?? data?['nationalId']),
          _fieldRow('الرقم التأميني', data?['insurance_number']),
          _fieldRow('تاريخ التعيين', data?['hire_date']),
          _fieldRow('الوظيفة', data?['job_title']),
          _fieldRow('الإدارة / القسم', data?['department'] ?? data?['department_name']),
        ],
      ),
    );
  }

  Widget _contactCard() {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFFFFFDF8),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0x22C9A24B)),
      ),
      child: Column(
        children: [
          const Padding(
            padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Align(
              alignment: Alignment.centerRight,
              child: Text(
                'جهات الاتصال',
                style: TextStyle(
                  color: EmployeePortalApp.navy,
                  fontWeight: FontWeight.w900,
                  fontSize: 15,
                ),
              ),
            ),
          ),
          _fieldRow('رقم الهاتف', data?['phone'] ?? data?['phone_number']),
          _fieldRow('البريد الإلكتروني', data?['email']),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (loading) return const Center(child: CircularProgressIndicator());
    if (error != null) return _ErrorView(message: error!, onRetry: load);
    if (data == null) return const Center(child: Text('لا توجد بيانات'));

    return RefreshIndicator(
      onRefresh: load,
      child: LayoutBuilder(
        builder: (context, c) {
          final desktop = c.maxWidth >= 820;
          return ListView(
            padding: const EdgeInsets.all(18),
            children: [
              if (desktop)
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _profileCard(),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        children: [
                          _detailsCard(),
                          const SizedBox(height: 14),
                          _contactCard(),
                        ],
                      ),
                    ),
                  ],
                )
              else ...[
                Center(child: _profileCard()),
                const SizedBox(height: 14),
                _detailsCard(),
                const SizedBox(height: 14),
                _contactCard(),
              ],
            ],
          );
        },
      ),
    );
  }
}

class PayslipPage extends StatefulWidget {
  const PayslipPage({super.key});

  @override
  State<PayslipPage> createState() => _PayslipPageState();
}

class _PayslipPageState extends State<PayslipPage> {
  int month = DateTime.now().month;
  int year = DateTime.now().year;
  Map<String, dynamic>? payslip;
  bool loading = false;
  String? error;

  final months = const [
    'يناير','فبراير','مارس','أبريل','مايو','يونيو',
    'يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر',
  ];

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
      payslip = null;
    });
    try {
      final response = await api.get('/api/payslip?month=$month&year=$year');
      final body = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(body['error'] ?? 'لا توجد بيانات لهذا الشهر');
      }
      if (body is Map<String, dynamic>) {
        if (mounted) setState(() => payslip = body);
      } else {
        throw Exception('صيغة بيانات شريط المرتب غير صحيحة');
      }
    } catch (e) {
      if (mounted) setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  void openPayslipPdf() {
    if (payslip == null || api.token == null) return;
    final url = '$apiBaseUrl/api/payslip/pdf?month=$month&year=$year&token=${Uri.encodeQueryComponent(api.token!)}';
    launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
  }

  List<Map<String, dynamic>> getItemsByType(String type) {
    final raw = payslip?['items'];
    if (raw is! List) return [];
    return raw
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .where((e) => e['type'] == type)
        .toList();
  }

  Widget _summary(String title, dynamic value, Color color) {
    return Container(
      constraints: const BoxConstraints(minWidth: 175),
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFDF8),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: .28)),
      ),
      child: Column(
        children: [
          Text(title, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w800)),
          const SizedBox(height: 5),
          Text('${money(value)}', style: TextStyle(color: color, fontSize: 21, fontWeight: FontWeight.w900)),
          const Text('جنيه', style: TextStyle(color: EmployeePortalApp.gray, fontSize: 10)),
        ],
      ),
    );
  }

  Widget _itemsTable(String title, List<Map<String, dynamic>> items, Color headerColor) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFFFFFDF8),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0x22C9A24B)),
      ),
      child: Column(
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 10),
            decoration: BoxDecoration(
              color: headerColor,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(11)),
            ),
            child: Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900),
            ),
          ),
          if (items.isEmpty)
            const Padding(
              padding: EdgeInsets.all(18),
              child: Text('لا توجد بنود'),
            )
          else
            ...items.map(
              (item) => Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                decoration: const BoxDecoration(
                  border: Border(bottom: BorderSide(color: Color(0xFFEDE5DA))),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        '${item['name'] ?? ''}',
                        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
                      ),
                    ),
                    Text(
                      money(item['amount']),
                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w900),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final earnings = getItemsByType('earning');
    final deductions = getItemsByType('deduction');
    final earningsTotal = payslip?['earnings_total'] ?? 0;
    final deductionsTotal = payslip?['deductions_total'] ?? 0;
    final net = payslip?['net_salary'] ?? (toDouble(earningsTotal) - toDouble(deductionsTotal));

    return Column(
      children: [
        _MonthYearSelector(
          month: month,
          year: year,
          months: months,
          onMonthChanged: (v) => setState(() => month = v),
          onYearChanged: (v) => setState(() => year = v),
          onRefresh: load,
          buttonLabel: 'عرض',
        ),
        Expanded(
          child: loading
              ? const Center(child: CircularProgressIndicator())
              : error != null
                  ? _ErrorView(message: error!, onRetry: load)
                  : payslip == null
                      ? const Center(child: Text('اختر الشهر والسنة ثم اضغط عرض'))
                      : RefreshIndicator(
                          onRefresh: load,
                          child: ListView(
                            padding: const EdgeInsets.all(16),
                            children: [
                              Wrap(
                                spacing: 12,
                                runSpacing: 12,
                                alignment: WrapAlignment.center,
                                children: [
                                  _summary('إجمالي الاستحقاقات', earningsTotal, const Color(0xFF21843B)),
                                  _summary('إجمالي الاستقطاعات', deductionsTotal, const Color(0xFFD71920)),
                                  _summary('إجمالي الصافي', net, const Color(0xFFB16F00)),
                                ],
                              ),
                              const SizedBox(height: 16),
                              LayoutBuilder(
                                builder: (context, c) {
                                  if (c.maxWidth >= 720) {
                                    return Row(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Expanded(child: _itemsTable('الاستحقاقات', earnings, const Color(0xFF2F7A3E))),
                                        const SizedBox(width: 14),
                                        Expanded(child: _itemsTable('الاستقطاعات', deductions, const Color(0xFFC81924))),
                                      ],
                                    );
                                  }
                                  return Column(
                                    children: [
                                      _itemsTable('الاستحقاقات', earnings, const Color(0xFF2F7A3E)),
                                      const SizedBox(height: 14),
                                      _itemsTable('الاستقطاعات', deductions, const Color(0xFFC81924)),
                                    ],
                                  );
                                },
                              ),
                              const SizedBox(height: 16),
                              Align(
                                alignment: Alignment.center,
                                child: SizedBox(
                                  width: 260,
                                  child: FilledButton.icon(
                                    onPressed: openPayslipPdf,
                                    icon: const Icon(Icons.download_rounded),
                                    label: const Text('تحميل PDF شريط المرتب'),
                                  ),
                                ),
                              ),
                              const SizedBox(height: 12),
                            ],
                          ),
                        ),
        ),
      ],
    );
  }
}

class WageRecordPage extends StatefulWidget {
  const WageRecordPage({super.key});

  @override
  State<WageRecordPage> createState() => _WageRecordPageState();
}

class _WageRecordPageState extends State<WageRecordPage> {
  int month = DateTime.now().month;
  int year = DateTime.now().year;
  bool loading = false;
  String? error;
  List<dynamic> data = [];

  final months = const [
    'يناير','فبراير','مارس','أبريل','مايو','يونيو',
    'يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر',
  ];

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
      data = [];
    });
    try {
      final response = await api.get('/api/wage-record?month=$month&year=$year');
      final body = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(body['error'] ?? 'لا يوجد سجل أجور لهذا الشهر');
      }
      final records = body['disbursements'];
      if (records is List) {
        if (mounted) setState(() => data = records);
      } else {
        throw Exception('صيغة سجل الأجور غير صحيحة');
      }
    } catch (e) {
      if (mounted) setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  void openWageRecordPdf() {
    if (api.token == null) return;
    final url = '$apiBaseUrl/api/wage-record/pdf?month=$month&year=$year&token=${Uri.encodeQueryComponent(api.token!)}';
    launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    final rows = data.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
    final earningsTotal = rows.fold<double>(0, (s, r) => s + toDouble(r['earnings_total']));
    final deductionsTotal = rows.fold<double>(0, (s, r) => s + toDouble(r['deductions_total']));
    final netTotal = rows.fold<double>(0, (s, r) => s + toDouble(r['net_salary']));

    Widget summary(String title, double value, Color color) {
      return Container(
        constraints: const BoxConstraints(minWidth: 180),
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
        decoration: BoxDecoration(
          color: const Color(0xFFFFFDF8),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withValues(alpha: .25)),
        ),
        child: Column(
          children: [
            Text(title, style: TextStyle(color: color, fontWeight: FontWeight.w800, fontSize: 12)),
            const SizedBox(height: 5),
            Text(money(value), style: TextStyle(color: color, fontWeight: FontWeight.w900, fontSize: 20)),
            const Text('جنيه', style: TextStyle(color: EmployeePortalApp.gray, fontSize: 10)),
          ],
        ),
      );
    }

    return Column(
      children: [
        _MonthYearSelector(
          month: month,
          year: year,
          months: months,
          onMonthChanged: (v) => setState(() => month = v),
          onYearChanged: (v) => setState(() => year = v),
          onRefresh: load,
          buttonLabel: 'بحث',
        ),
        Expanded(
          child: loading
              ? const Center(child: CircularProgressIndicator())
              : error != null
                  ? _ErrorView(message: error!, onRetry: load)
                  : RefreshIndicator(
                      onRefresh: load,
                      child: ListView(
                        padding: const EdgeInsets.all(16),
                        children: [
                          Wrap(
                            spacing: 12,
                            runSpacing: 12,
                            alignment: WrapAlignment.center,
                            children: [
                              summary('إجمالي الاستحقاقات', earningsTotal, const Color(0xFF21843B)),
                              summary('إجمالي الاستقطاعات', deductionsTotal, const Color(0xFFD71920)),
                              summary('إجمالي الصافي', netTotal, const Color(0xFFB16F00)),
                            ],
                          ),
                          const SizedBox(height: 16),
                          if (rows.isEmpty)
                            const Padding(
                              padding: EdgeInsets.all(42),
                              child: Center(child: Text('لا توجد بيانات لهذا الشهر')),
                            )
                          else
                            Container(
                              decoration: BoxDecoration(
                                color: const Color(0xFFFFFDF8),
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(color: const Color(0x22C9A24B)),
                              ),
                              child: SingleChildScrollView(
                                scrollDirection: Axis.horizontal,
                                child: DataTable(
                                  headingRowColor: WidgetStateProperty.all(const Color(0xFFF1E7DB)),
                                  columns: const [
                                    DataColumn(label: Text('الصرفية')),
                                    DataColumn(label: Text('إجمالي الاستحقاقات')),
                                    DataColumn(label: Text('إجمالي الاستقطاعات')),
                                    DataColumn(label: Text('الصافي')),
                                    DataColumn(label: Text('حالة الشريط')),
                                  ],
                                  rows: rows.map((r) {
                                    return DataRow(
                                      cells: [
                                        DataCell(Text('${r['sarfia_no'] ?? '-'}')),
                                        DataCell(Text(money(r['earnings_total']))),
                                        DataCell(Text(money(r['deductions_total']))),
                                        DataCell(Text(money(r['net_salary']))),
                                        const DataCell(
                                          Text(
                                            'متاح',
                                            style: TextStyle(color: EmployeePortalApp.green, fontWeight: FontWeight.w900),
                                          ),
                                        ),
                                      ],
                                    );
                                  }).toList(),
                                ),
                              ),
                            ),
                          const SizedBox(height: 18),
                          Align(
                            alignment: Alignment.center,
                            child: SizedBox(
                              width: 280,
                              child: OutlinedButton.icon(
                                onPressed: rows.isEmpty ? null : openWageRecordPdf,
                                icon: const Icon(Icons.download_rounded),
                                label: const Text('تحميل التقرير PDF'),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
        ),
      ],
    );
  }
}

class _MonthYearSelector extends StatelessWidget {
  final int month;
  final int year;
  final List<String> months;
  final ValueChanged<int> onMonthChanged;
  final ValueChanged<int> onYearChanged;
  final VoidCallback onRefresh;
  final String buttonLabel;

  const _MonthYearSelector({
    required this.month,
    required this.year,
    required this.months,
    required this.onMonthChanged,
    required this.onYearChanged,
    required this.onRefresh,
    this.buttonLabel = 'عرض',
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.fromLTRB(14, 14, 14, 4),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFDF8),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0x22C9A24B)),
        boxShadow: const [
          BoxShadow(color: Color(0x12000000), blurRadius: 12, offset: Offset(0, 4)),
        ],
      ),
      child: Wrap(
        spacing: 10,
        runSpacing: 10,
        crossAxisAlignment: WrapCrossAlignment.center,
        alignment: WrapAlignment.center,
        children: [
          SizedBox(
            width: 190,
            child: DropdownButtonFormField<int>(
              value: month,
              decoration: const InputDecoration(labelText: 'اختر الشهر', isDense: true),
              items: List.generate(
                12,
                (i) => DropdownMenuItem(value: i + 1, child: Text(months[i])),
              ),
              onChanged: (v) {
                if (v != null) onMonthChanged(v);
              },
            ),
          ),
          SizedBox(
            width: 150,
            child: DropdownButtonFormField<int>(
              value: year,
              decoration: const InputDecoration(labelText: 'اختر السنة', isDense: true),
              items: [2024, 2025, 2026, 2027, 2028]
                  .map((y) => DropdownMenuItem(value: y, child: Text('$y')))
                  .toList(),
              onChanged: (v) {
                if (v != null) onYearChanged(v);
              },
            ),
          ),
          SizedBox(
            width: 110,
            height: 50,
            child: FilledButton(
              onPressed: onRefresh,
              child: Text(buttonLabel),
            ),
          ),
        ],
      ),
    );
  }
}

class AdminDashboardPage extends StatelessWidget {
  const AdminDashboardPage({super.key});

  void _open(BuildContext context, Widget page) {
    Navigator.push(context, MaterialPageRoute(builder: (_) => page));
  }

  @override
  Widget build(BuildContext context) {
    final items = [
      (
        Icons.people_alt_outlined,
        'إدارة الموظفين',
        'بحث، عرض وتعديل البيانات وإعادة كلمة المرور',
        const AdminEmployeesPage(),
      ),
      (
        Icons.forum_outlined,
        'رسائل الموظفين',
        'عرض المحادثات والرد على الموظفين',
        const AdminMessagesPage(),
      ),
      (
        Icons.campaign_outlined,
        'الإشعارات',
        'نشر إشعار عام أو لموظف محدد وإدارة المنشور',
        const AdminAnnouncementsPage(),
      ),
      (
        Icons.star_outline,
        'تقييمات الخدمة',
        'متوسط التقييم وآراء الموظفين',
        const AdminRatingsPage(),
      ),
      (
        Icons.history,
        'سجل العمليات',
        'مراجعة أهم عمليات الأدمن المسجلة',
        const AdminAuditLogPage(),
      ),
    ];

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF74162A), Color(0xFF4A0D19)],
            ),
            borderRadius: BorderRadius.circular(22),
            border: Border.all(color: EmployeePortalApp.gold.withValues(alpha: .5)),
            boxShadow: const [
              BoxShadow(color: Color(0x55000000), blurRadius: 18, offset: Offset(0, 8)),
            ],
          ),
          child: const Row(
            children: [
              CircleAvatar(
                backgroundColor: EmployeePortalApp.gold,
                foregroundColor: EmployeePortalApp.navy,
                child: Icon(Icons.admin_panel_settings),
              ),
              SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'لوحة تحكم الموارد البشرية',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    SizedBox(height: 4),
                    Text(
                      'الأدوات الإدارية المتاحة لحساب HR Admin فقط',
                      style: TextStyle(color: Colors.white70),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),
        ...items.map(
          (item) => Card(
            margin: const EdgeInsets.only(bottom: 10),
            color: const Color(0xFFFFF4DF),
            child: ListTile(
              contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
              onTap: () => _open(context, item.$4),
              leading: CircleAvatar(
                backgroundColor: EmployeePortalApp.goldSoft,
                foregroundColor: EmployeePortalApp.navy,
                child: Icon(item.$1),
              ),
              title: Text(
                item.$2,
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
              subtitle: Text(item.$3),
              trailing: const Icon(Icons.arrow_back_ios_new, size: 16),
            ),
          ),
        ),
      ],
    );
  }
}

class AdminEmployeesPage extends StatefulWidget {
  const AdminEmployeesPage({super.key});

  @override
  State<AdminEmployeesPage> createState() => _AdminEmployeesPageState();
}

class _AdminEmployeesPageState extends State<AdminEmployeesPage> {
  final search = TextEditingController();
  List<Map<String, dynamic>> results = [];
  bool loading = false;
  String? error;

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  Future<void> doSearch() async {
    final q = search.text.trim();
    if (q.isEmpty) {
      setState(() => error = 'اكتب كود العامل أو اسم الموظف');
      return;
    }

    setState(() {
      loading = true;
      error = null;
    });

    try {
      final response = await api.get(
        '/api/admin/employees?search=${Uri.encodeQueryComponent(q)}',
      );
      final body = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(body['error'] ?? 'تعذر البحث');
      }

      setState(() {
        results = (body as List)
            .whereType<Map>()
            .map((e) => Map<String, dynamic>.from(e))
            .toList();
      });
    } catch (e) {
      setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(title: const Text('إدارة الموظفين')),
        body: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: search,
                      textInputAction: TextInputAction.search,
                      onSubmitted: (_) => doSearch(),
                      decoration: const InputDecoration(
                        labelText: 'كود العامل أو الاسم',
                        prefixIcon: Icon(Icons.search),
                        border: OutlineInputBorder(),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(
                    tooltip: 'بحث',
                    onPressed: loading ? null : doSearch,
                    icon: const Icon(Icons.search),
                  ),
                ],
              ),
            ),
            if (loading) const LinearProgressIndicator(),
            if (error != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Text(
                  error!,
                  style: const TextStyle(color: EmployeePortalApp.red),
                ),
              ),
            Expanded(
              child: results.isEmpty
                  ? const Center(child: Text('ابحث عن موظف لعرض بياناته'))
                  : ListView.builder(
                      padding: const EdgeInsets.all(12),
                      itemCount: results.length,
                      itemBuilder: (_, i) {
                        final e = results[i];
                        return Card(
                          child: ListTile(
                            onTap: () async {
                              await Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => AdminEmployeeDetailsPage(
                                    employeeId: e['id'] as int,
                                  ),
                                ),
                              );
                              if (search.text.trim().isNotEmpty) doSearch();
                            },
                            leading: CircleAvatar(
                              backgroundColor: EmployeePortalApp.goldSoft,
                              foregroundColor: EmployeePortalApp.navy,
                              child: Text(
                                '${e['full_name'] ?? '?'}'.trim().isEmpty
                                    ? '?'
                                    : '${e['full_name']}'.trim().substring(0, 1),
                              ),
                            ),
                            title: Text(
                              '${e['full_name'] ?? ''}',
                              style: const TextStyle(fontWeight: FontWeight.w800),
                            ),
                            subtitle: Text(
                              'كود: ${e['employee_code'] ?? ''}\n'
                              '${e['job_title'] ?? ''}',
                            ),
                            isThreeLine: true,
                            trailing: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(
                                  e['status'] == 'active'
                                      ? Icons.check_circle
                                      : Icons.pause_circle,
                                  color: e['status'] == 'active'
                                      ? EmployeePortalApp.green
                                      : EmployeePortalApp.red,
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class AdminEmployeeDetailsPage extends StatefulWidget {
  final int employeeId;

  const AdminEmployeeDetailsPage({
    super.key,
    required this.employeeId,
  });

  @override
  State<AdminEmployeeDetailsPage> createState() => _AdminEmployeeDetailsPageState();
}

class _AdminEmployeeDetailsPageState extends State<AdminEmployeeDetailsPage> {
  final fullName = TextEditingController();
  final jobTitle = TextEditingController();
  final phone = TextEditingController();
  final nationalId = TextEditingController();

  Map<String, dynamic>? data;
  String status = 'active';
  bool loading = true;
  bool saving = false;
  String? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    fullName.dispose();
    jobTitle.dispose();
    phone.dispose();
    nationalId.dispose();
    super.dispose();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });

    try {
      final response = await api.get('/api/admin/employees/${widget.employeeId}');
      final body = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(body['error'] ?? 'تعذر تحميل بيانات الموظف');
      }

      final map = Map<String, dynamic>.from(body);
      fullName.text = '${map['full_name'] ?? ''}';
      jobTitle.text = '${map['job_title'] ?? ''}';
      phone.text = '${map['phone'] ?? ''}';
      nationalId.text = '${map['national_id'] ?? ''}';
      status = '${map['status'] ?? 'active'}';

      setState(() => data = map);
    } catch (e) {
      setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> save() async {
    setState(() {
      saving = true;
      error = null;
    });

    try {
      final response = await api.put(
        '/api/admin/employees/${widget.employeeId}',
        {
          'full_name': fullName.text.trim(),
          'job_title': jobTitle.text.trim(),
          'phone': phone.text.trim(),
          'status': status,
          'national_id': nationalId.text.trim(),
        },
      );
      final body = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(body['error'] ?? 'تعذر حفظ البيانات');
      }

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${body['message'] ?? 'تم الحفظ بنجاح'}')),
      );
      await load();
    } catch (e) {
      setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  Future<void> resetPassword() async {
    final controller = TextEditingController(text: 'Welcome123');
    final newPassword = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('إعادة تعيين كلمة المرور'),
        content: TextField(
          controller: controller,
          obscureText: true,
          decoration: const InputDecoration(
            labelText: 'كلمة المرور الجديدة',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text.trim()),
            child: const Text('تنفيذ'),
          ),
        ],
      ),
    );
    controller.dispose();

    if (newPassword == null || newPassword.isEmpty) return;

    try {
      final response = await api.post(
        '/api/admin/employees/${widget.employeeId}/reset-password',
        {'new_password': newPassword},
      );
      final body = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(body['error'] ?? 'تعذر إعادة كلمة المرور');
      }
      if (!mounted) return;
      showDialog(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('تمت العملية'),
          content: SelectableText(
            '${body['message'] ?? 'تم تغيير كلمة المرور'}\n\n'
            'كلمة المرور الجديدة: ${body['new_password'] ?? newPassword}',
          ),
          actions: [
            FilledButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('تم'),
            ),
          ],
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(cleanError(e))),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(title: const Text('بيانات الموظف')),
        body: loading
            ? const Center(child: CircularProgressIndicator())
            : error != null && data == null
                ? _ErrorView(message: error!, onRetry: load)
                : ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      if (data != null)
                        Card(
                          child: ListTile(
                            leading: const Icon(
                              Icons.badge,
                              color: EmployeePortalApp.navy,
                            ),
                            title: Text('${data!['employee_code'] ?? ''}'),
                            subtitle: Text(
                              '${data!['department_name'] ?? 'بدون إدارة'}'
                              '${data!['email'] == null ? '' : '\n${data!['email']}'}',
                            ),
                          ),
                        ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: fullName,
                        decoration: const InputDecoration(
                          labelText: 'الاسم',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: jobTitle,
                        decoration: const InputDecoration(
                          labelText: 'الوظيفة',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: phone,
                        keyboardType: TextInputType.phone,
                        decoration: const InputDecoration(
                          labelText: 'رقم الهاتف',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: nationalId,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'الرقم القومي',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 10),
                      DropdownButtonFormField<String>(
                        value: status,
                        decoration: const InputDecoration(
                          labelText: 'حالة الحساب',
                          border: OutlineInputBorder(),
                        ),
                        items: const [
                          DropdownMenuItem(value: 'active', child: Text('ساري')),
                          DropdownMenuItem(value: 'inactive', child: Text('موقوف')),
                        ],
                        onChanged: (v) {
                          if (v != null) setState(() => status = v);
                        },
                      ),
                      if (error != null) ...[
                        const SizedBox(height: 10),
                        Text(
                          error!,
                          style: const TextStyle(color: EmployeePortalApp.red),
                        ),
                      ],
                      const SizedBox(height: 14),
                      FilledButton.icon(
                        onPressed: saving ? null : save,
                        icon: saving
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.white,
                                ),
                              )
                            : const Icon(Icons.save),
                        label: const Text('حفظ التعديلات'),
                      ),
                      const SizedBox(height: 10),
                      OutlinedButton.icon(
                        onPressed: resetPassword,
                        icon: const Icon(Icons.password),
                        label: const Text('إعادة تعيين كلمة المرور'),
                      ),
                    ],
                  ),
      ),
    );
  }
}

class AdminMessagesPage extends StatefulWidget {
  const AdminMessagesPage({super.key});

  @override
  State<AdminMessagesPage> createState() => _AdminMessagesPageState();
}

class _AdminMessagesPageState extends State<AdminMessagesPage> {
  List<Map<String, dynamic>> threads = [];
  bool loading = true;
  String? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final response = await api.get('/api/admin/messages');
      final body = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(body['error'] ?? 'تعذر تحميل الرسائل');
      }
      setState(() {
        threads = (body as List)
            .whereType<Map>()
            .map((e) => Map<String, dynamic>.from(e))
            .toList();
      });
    } catch (e) {
      setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('رسائل الموظفين'),
          actions: [
            IconButton(onPressed: load, icon: const Icon(Icons.refresh)),
          ],
        ),
        body: loading
            ? const Center(child: CircularProgressIndicator())
            : error != null
                ? _ErrorView(message: error!, onRetry: load)
                : RefreshIndicator(
                    onRefresh: load,
                    child: ListView.builder(
                      padding: const EdgeInsets.all(12),
                      itemCount: threads.length,
                      itemBuilder: (_, i) {
                        final t = threads[i];
                        final unread = (t['unread_count'] as num?)?.toInt() ?? 0;
                        return Card(
                          child: ListTile(
                            onTap: () async {
                              await Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) => AdminThreadPage(
                                    threadId: t['thread_id'] as int,
                                  ),
                                ),
                              );
                              load();
                            },
                            leading: CircleAvatar(
                              backgroundColor: unread > 0
                                  ? EmployeePortalApp.gold
                                  : EmployeePortalApp.goldSoft,
                              foregroundColor: EmployeePortalApp.navy,
                              child: unread > 0
                                  ? Text('$unread')
                                  : const Icon(Icons.person),
                            ),
                            title: Text(
                              '${t['full_name'] ?? ''}',
                              style: const TextStyle(fontWeight: FontWeight.w800),
                            ),
                            subtitle: Text(
                              'كود: ${t['employee_code'] ?? ''}\n'
                              '${t['last_body'] ?? ''}',
                              maxLines: 3,
                              overflow: TextOverflow.ellipsis,
                            ),
                            isThreeLine: true,
                            trailing: Text(
                              '${t['updated_at'] ?? ''}',
                              style: const TextStyle(fontSize: 10),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
      ),
    );
  }
}

class AdminThreadPage extends StatefulWidget {
  final int threadId;

  const AdminThreadPage({
    super.key,
    required this.threadId,
  });

  @override
  State<AdminThreadPage> createState() => _AdminThreadPageState();
}

class _AdminThreadPageState extends State<AdminThreadPage> {
  final reply = TextEditingController();
  Map<String, dynamic>? data;
  bool loading = true;
  bool sending = false;
  String? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    reply.dispose();
    super.dispose();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final response = await api.get('/api/admin/messages/${widget.threadId}');
      final body = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(body['error'] ?? 'تعذر تحميل المحادثة');
      }
      setState(() => data = Map<String, dynamic>.from(body));
    } catch (e) {
      setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> sendReply() async {
    final text = reply.text.trim();
    if (text.isEmpty) return;

    setState(() => sending = true);
    try {
      final response = await api.post(
        '/api/admin/messages/${widget.threadId}/reply',
        {'reply': text},
      );
      final body = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(body['error'] ?? 'تعذر إرسال الرد');
      }
      reply.clear();
      await load();
    } catch (e) {
      if (mounted) setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  Future<bool> _confirm(String title, String message) async {
    return await showDialog<bool>(
          context: context,
          builder: (_) => AlertDialog(
            title: Text(title),
            content: Text(message),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('إلغاء'),
              ),
              FilledButton(
                style: FilledButton.styleFrom(backgroundColor: EmployeePortalApp.red),
                onPressed: () => Navigator.pop(context, true),
                child: const Text('حذف نهائي'),
              ),
            ],
          ),
        ) ??
        false;
  }

  Future<void> deleteMessage(int messageId) async {
    final confirmed = await _confirm(
      'حذف الرسالة',
      'سيتم حذف هذه الرسالة من المحادثة عند الموظف والمسؤول. هل أنت متأكد؟',
    );
    if (!confirmed) return;

    try {
      final response = await api.delete(
        '/api/admin/messages/${widget.threadId}/messages/$messageId',
      );
      final body = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(body['error'] ?? 'تعذر حذف الرسالة');
      }
      await load();
    } catch (e) {
      if (mounted) setState(() => error = cleanError(e));
    }
  }

  Future<void> deleteConversation() async {
    final confirmed = await _confirm(
      'حذف المحادثة بالكامل',
      'سيتم حذف كل الرسائل نهائيًا عند الطرفين. لا يمكن التراجع عن هذه العملية.',
    );
    if (!confirmed) return;

    try {
      final response = await api.delete('/api/admin/messages/${widget.threadId}');
      final body = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(body['error'] ?? 'تعذر حذف المحادثة');
      }
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) setState(() => error = cleanError(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final messages = data?['messages'] is List
        ? (data!['messages'] as List)
            .whereType<Map>()
            .map((e) => Map<String, dynamic>.from(e))
            .toList()
        : <Map<String, dynamic>>[];

    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(
          title: Text(data == null ? 'المحادثة' : '${data!['full_name'] ?? ''}'),
          actions: [
            IconButton(
              tooltip: 'حذف المحادثة بالكامل',
              onPressed: data == null ? null : deleteConversation,
              icon: const Icon(Icons.delete_forever_outlined),
            ),
          ],
        ),
        body: loading
            ? const Center(child: CircularProgressIndicator())
            : error != null && data == null
                ? _ErrorView(message: error!, onRetry: load)
                : Column(
                    children: [
                      if (data != null)
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(10),
                          color: EmployeePortalApp.goldSoft,
                          child: Text(
                            'كود العامل: ${data!['employee_code'] ?? ''}',
                            textAlign: TextAlign.center,
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                        ),
                      Expanded(
                        child: ListView.builder(
                          padding: const EdgeInsets.all(12),
                          itemCount: messages.length,
                          itemBuilder: (_, i) {
                            final m = messages[i];
                            final admin = m['sender_role'] == 'admin';
                            return Align(
                              alignment: admin
                                  ? Alignment.centerRight
                                  : Alignment.centerLeft,
                              child: Container(
                                constraints: const BoxConstraints(maxWidth: 320),
                                margin: const EdgeInsets.only(bottom: 8),
                                padding: const EdgeInsets.all(11),
                                decoration: BoxDecoration(
                                  color: admin
                                      ? EmployeePortalApp.navy
                                      : Colors.white,
                                  borderRadius: BorderRadius.circular(12),
                                  border: admin
                                      ? null
                                      : Border.all(color: EmployeePortalApp.line),
                                ),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      '${m['body'] ?? ''}',
                                      style: TextStyle(
                                        color: admin ? Colors.white : Colors.black87,
                                      ),
                                    ),
                                    const SizedBox(height: 5),
                                    Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Text(
                                          '${m['created_at'] ?? ''}',
                                          style: TextStyle(
                                            fontSize: 10,
                                            color: admin
                                                ? Colors.white60
                                                : EmployeePortalApp.gray,
                                          ),
                                        ),
                                        const SizedBox(width: 8),
                                        InkWell(
                                          onTap: () => deleteMessage(m['id'] as int),
                                          child: Icon(
                                            Icons.delete_outline,
                                            size: 17,
                                            color: admin ? Colors.white70 : EmployeePortalApp.red,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                              ),
                            );
                          },
                        ),
                      ),
                      if (error != null)
                        Padding(
                          padding: const EdgeInsets.all(6),
                          child: Text(
                            error!,
                            style: const TextStyle(color: EmployeePortalApp.red),
                          ),
                        ),
                      SafeArea(
                        top: false,
                        child: Padding(
                          padding: const EdgeInsets.all(10),
                          child: Row(
                            children: [
                              Expanded(
                                child: TextField(
                                  controller: reply,
                                  minLines: 1,
                                  maxLines: 4,
                                  decoration: const InputDecoration(
                                    hintText: 'اكتب الرد...',
                                    border: OutlineInputBorder(),
                                  ),
                                ),
                              ),
                              const SizedBox(width: 8),
                              IconButton.filled(
                                onPressed: sending ? null : sendReply,
                                icon: sending
                                    ? const SizedBox(
                                        width: 18,
                                        height: 18,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          color: Colors.white,
                                        ),
                                      )
                                    : const Icon(Icons.send),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
      ),
    );
  }
}

class AdminAnnouncementsPage extends StatefulWidget {
  const AdminAnnouncementsPage({super.key});

  @override
  State<AdminAnnouncementsPage> createState() => _AdminAnnouncementsPageState();
}

class _AdminAnnouncementsPageState extends State<AdminAnnouncementsPage> {
  final title = TextEditingController();
  final body = TextEditingController();
  final targetCode = TextEditingController();
  List<Map<String, dynamic>> announcements = [];
  bool loading = true;
  bool sending = false;
  String? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    title.dispose();
    body.dispose();
    targetCode.dispose();
    super.dispose();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final response = await api.get('/api/admin/announcements/list');
      final decoded = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(decoded['error'] ?? 'تعذر تحميل الإشعارات');
      }
      setState(() {
        announcements = (decoded as List)
            .whereType<Map>()
            .map((e) => Map<String, dynamic>.from(e))
            .toList();
      });
    } catch (e) {
      setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> publish() async {
    if (title.text.trim().isEmpty) {
      setState(() => error = 'عنوان الإشعار مطلوب');
      return;
    }

    setState(() {
      sending = true;
      error = null;
    });

    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$apiBaseUrl/api/admin/announcements'),
      );
      if (api.token != null) {
        request.headers['Authorization'] = 'Bearer ${api.token}';
      }
      request.headers['ngrok-skip-browser-warning'] = 'true';
      request.fields['title'] = title.text.trim();
      request.fields['body'] = body.text.trim();
      request.fields['target_employee_code'] = targetCode.text.trim();

      final streamed = await request.send();
      final response = await http.Response.fromStream(streamed);
      final decoded = jsonDecode(response.body);

      if (response.statusCode != 200) {
        throw Exception(decoded['error'] ?? 'تعذر نشر الإشعار');
      }

      title.clear();
      body.clear();
      targetCode.clear();

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${decoded['message'] ?? 'تم نشر الإشعار'}')),
      );
      await load();
    } catch (e) {
      if (mounted) setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  Future<void> remove(int id) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('حذف الإشعار'),
        content: const Text('هل أنت متأكد من حذف هذا الإشعار؟'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('حذف'),
          ),
        ],
      ),
    );

    if (ok != true) return;

    try {
      final response = await api.delete('/api/admin/announcements/$id');
      final decoded = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(decoded['error'] ?? 'تعذر حذف الإشعار');
      }
      await load();
    } catch (e) {
      if (mounted) setState(() => error = cleanError(e));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(title: const Text('إدارة الإشعارات')),
        body: ListView(
          padding: const EdgeInsets.all(14),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  children: [
                    TextField(
                      controller: title,
                      decoration: const InputDecoration(
                        labelText: 'عنوان الإشعار',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: body,
                      minLines: 3,
                      maxLines: 6,
                      decoration: const InputDecoration(
                        labelText: 'نص الإشعار',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: targetCode,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: 'كود موظف محدد - اتركه فارغًا للإشعار العام',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    if (error != null) ...[
                      const SizedBox(height: 8),
                      Text(
                        error!,
                        style: const TextStyle(color: EmployeePortalApp.red),
                      ),
                    ],
                    const SizedBox(height: 10),
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: sending ? null : publish,
                        icon: const Icon(Icons.send),
                        label: Text(sending ? 'جاري النشر...' : 'نشر الإشعار'),
                      ),
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      'إرفاق الصور وPDF يظل متاحًا من لوحة الويب الحالية.',
                      style: TextStyle(
                        color: EmployeePortalApp.gray,
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            const Text(
              'الإشعارات المنشورة',
              style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 6),
            if (loading)
              const Center(child: CircularProgressIndicator())
            else
              ...announcements.map(
                (a) => Card(
                  child: ListTile(
                    title: Text(
                      '${a['title'] ?? ''}',
                      style: const TextStyle(fontWeight: FontWeight.w800),
                    ),
                    subtitle: Text(
                      '${a['body'] ?? ''}\n'
                      '${a['target_name'] == null ? 'عام لكل الموظفين' : 'إلى: ${a['target_name']}'}'
                      ' • إعجاب: ${a['like_count'] ?? 0}\n'
                      '${a['created_at'] ?? ''}',
                    ),
                    isThreeLine: true,
                    trailing: IconButton(
                      tooltip: 'حذف',
                      onPressed: () => remove(a['id'] as int),
                      icon: const Icon(Icons.delete_outline, color: EmployeePortalApp.red),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class AdminRatingsPage extends StatefulWidget {
  const AdminRatingsPage({super.key});

  @override
  State<AdminRatingsPage> createState() => _AdminRatingsPageState();
}

class _AdminRatingsPageState extends State<AdminRatingsPage> {
  Map<String, dynamic>? data;
  bool loading = true;
  String? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final response = await api.get('/api/admin/service-ratings');
      final decoded = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(decoded['error'] ?? 'تعذر تحميل التقييمات');
      }
      setState(() => data = Map<String, dynamic>.from(decoded));
    } catch (e) {
      setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ratings = data?['ratings'] is List
        ? (data!['ratings'] as List)
            .whereType<Map>()
            .map((e) => Map<String, dynamic>.from(e))
            .toList()
        : <Map<String, dynamic>>[];

    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('تقييمات الخدمة'),
          actions: [
            IconButton(onPressed: load, icon: const Icon(Icons.refresh)),
          ],
        ),
        body: loading
            ? const Center(child: CircularProgressIndicator())
            : error != null
                ? _ErrorView(message: error!, onRetry: load)
                : ListView(
                    padding: const EdgeInsets.all(14),
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: _AdminStatCard(
                              title: 'متوسط التقييم',
                              value: '${data?['average'] ?? '-'} / 5',
                              icon: Icons.star,
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: _AdminStatCard(
                              title: 'عدد التقييمات',
                              value: '${data?['total'] ?? 0}',
                              icon: Icons.reviews,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      ...ratings.map(
                        (r) => Card(
                          child: ListTile(
                            leading: CircleAvatar(
                              backgroundColor: EmployeePortalApp.goldSoft,
                              foregroundColor: EmployeePortalApp.navy,
                              child: Text('${r['rating'] ?? 0}★'),
                            ),
                            title: Text(
                              '${r['full_name'] ?? ''}',
                              style: const TextStyle(fontWeight: FontWeight.w800),
                            ),
                            subtitle: Text(
                              'كود: ${r['employee_code'] ?? ''}\n'
                              '${r['comment'] ?? 'بدون تعليق'}\n'
                              '${r['created_at'] ?? ''}',
                            ),
                            isThreeLine: true,
                          ),
                        ),
                      ),
                    ],
                  ),
      ),
    );
  }
}

class _AdminStatCard extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;

  const _AdminStatCard({
    required this.title,
    required this.value,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          children: [
            Icon(icon, color: EmployeePortalApp.gold, size: 30),
            const SizedBox(height: 6),
            Text(
              value,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: EmployeePortalApp.navy,
                fontSize: 20,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 3),
            Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(color: EmployeePortalApp.gray),
            ),
          ],
        ),
      ),
    );
  }
}

class AdminAuditLogPage extends StatefulWidget {
  const AdminAuditLogPage({super.key});

  @override
  State<AdminAuditLogPage> createState() => _AdminAuditLogPageState();
}

class _AdminAuditLogPageState extends State<AdminAuditLogPage> {
  List<Map<String, dynamic>> rows = [];
  bool loading = true;
  String? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final response = await api.get('/api/admin/audit-log');
      final decoded = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(decoded['error'] ?? 'تعذر تحميل سجل العمليات');
      }
      setState(() {
        rows = (decoded as List)
            .whereType<Map>()
            .map((e) => Map<String, dynamic>.from(e))
            .toList();
      });
    } catch (e) {
      setState(() => error = cleanError(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('سجل العمليات'),
          actions: [
            IconButton(onPressed: load, icon: const Icon(Icons.refresh)),
          ],
        ),
        body: loading
            ? const Center(child: CircularProgressIndicator())
            : error != null
                ? _ErrorView(message: error!, onRetry: load)
                : ListView.builder(
                    padding: const EdgeInsets.all(12),
                    itemCount: rows.length,
                    itemBuilder: (_, i) {
                      final r = rows[i];
                      return Card(
                        child: ListTile(
                          leading: const CircleAvatar(
                            backgroundColor: EmployeePortalApp.goldSoft,
                            foregroundColor: EmployeePortalApp.navy,
                            child: Icon(Icons.history),
                          ),
                          title: Text(
                            '${r['action_type'] ?? ''}',
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                          subtitle: Text(
                            'الأدمن: ${r['admin_name'] ?? ''} (${r['admin_code'] ?? ''})\n'
                            '${r['target_name'] == null ? '' : 'الموظف: ${r['target_name']} (${r['target_code'] ?? ''})\n'}'
                            '${r['details'] ?? ''}\n'
                            '${r['created_at'] ?? ''}',
                          ),
                          isThreeLine: true,
                        ),
                      );
                    },
                  ),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _ErrorView({
    required this.message,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.error_outline,
              size: 54,
              color: Colors.red.shade400,
            ),
            const SizedBox(height: 12),
            Text(
              message,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 18),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('إعادة المحاولة'),
            ),
          ],
        ),
      ),
    );
  }
}
