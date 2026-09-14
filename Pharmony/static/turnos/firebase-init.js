if (typeof firebase !== 'undefined' && !firebase.apps.length) {
  if (typeof firebaseConfig !== 'undefined') {
    firebase.initializeApp(firebaseConfig);
  }
}

const dbFirestore = (typeof firebase !== 'undefined' && firebase.apps.length) ? firebase.firestore() : null;
