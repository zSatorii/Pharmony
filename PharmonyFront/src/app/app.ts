import { Component, OnInit } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { DjangoApiService } from './services/django-api'; // Asegúrate de que la ruta apunte a tu servicio
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, CommonModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent implements OnInit {
  mensajeDesdeDjango: string = 'Cargando conexión...';

  constructor(private apiService: DjangoApiService) { }

  ngOnInit() {
    // Al cargar la página, llamamos a Django
    this.apiService.getTest().subscribe({
      next: (data) => {
        // Si Django responde con un JSON, aquí guardamos el mensaje
        this.mensajeDesdeDjango = data.mensaje || JSON.stringify(data);
      },
      error: (err) => {
        console.error(err);
        this.mensajeDesdeDjango = 'Error al conectar con el servidor de Django';
      }
    });
  }
}