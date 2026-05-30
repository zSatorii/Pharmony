import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class DjangoApiService {
  // Aquí pones la URL de tu backend de Django
  private apiUrl = 'http://127.0.0.1:8000/';

  constructor(private http: HttpClient) { }

  // Este método irá a buscar lo que sea que responda Django en la raíz
  getTest(): Observable<any> {
    return this.http.get(this.apiUrl);
  }
}