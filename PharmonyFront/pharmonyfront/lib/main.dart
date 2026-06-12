import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

void main(){
  runApp(MyApp());
}


class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: _ProductosScreen(),
    );
  }
}

class _ProductosScreen extends StatefulWidget {
  @override
  _ProductosScreenState createState() => _ProductosScreenState();
}

class _ProductosScreenState extends State<_ProductosScreen> {
  List productos = [];

  @override
  void initState() {
    super.initState();
    fetchProductos();
  }

  Future<void> fetchProductos() async {
    // ⚠️ REVISA EL TIP DE IP ABAJO ANTES DE PROBAR
    final url = Uri.parse('http://localhost:8000/api/productos/'); 
    
    try {
      final response = await http.get(url);
      if (response.statusCode == 200) {
        setState(() {
          productos = json.decode(response.body);
        });
      } else {
        print('Error en el servidor: ${response.statusCode}');
      }
    } catch (e) {
      print('Error de conexión: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Productos desde Django')),
      body: productos.isEmpty
          ? Center(child: CircularProgressIndicator())
          : ListView.builder(
              itemCount: productos.length,
              itemBuilder: (context, index) {
                return ListTile(
                  title: Text(productos[index]['nombre']),
                  subtitle: Text('\$${productos[index]['precio']}'),
                );
              },
            ),
    );
  }
}