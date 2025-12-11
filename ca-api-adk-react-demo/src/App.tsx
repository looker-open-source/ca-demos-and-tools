import React, { useEffect } from 'react';
import logo from './logo.svg';
import './App.css';
import { ComponentsProvider } from '@looker/components-providers';
import { apiClient } from './services/clientService';



function App() {



  // 2. Use useEffect with an empty dependency array [] to run once on mount

  useEffect(() => {

    const fetchData = async () => {

      try {

        // We call the generic get. 

        // Note: Your clientService currently hardcodes the URL to '/list-apps' 

        // and handles the console.log internally.

        await apiClient.get('/list-apps');

      } catch (error) {

        console.error("Failed to fetch initial data:", error);

      }

    };



    fetchData();

  }, []);



  return (

    <ComponentsProvider>

      <div className="App">

        <header className="App-header">

          <img src={logo} className="App-logo" alt="logo" />

          <p>

            Edit <code>src/App.tsx</code> and save to reload.

          </p>

          <a

            className="App-link"

            href="https://reactjs.org"

            target="_blank"

            rel="noopener noreferrer"

          >

            Learn React

          </a>

        </header>

      </div>

    </ComponentsProvider>

  );

}



export default App;