import { TestBed } from '@angular/core/testing';

import { DjangoApi } from './django-api';

describe('DjangoApi', () => {
  let service: DjangoApi;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(DjangoApi);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
